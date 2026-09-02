from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from attachments.models import Attachment
from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from workorders.models import WorkOrder

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"safe-image-content"


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def attachment_accounts(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.ATTACHMENT_MAX_BYTES = 1024
    alpha = Organisation.objects.create(
        name="Alpha Attachments",
        slug="alpha-attachments",
        storage_limit_bytes=4096,
    )
    beta = Organisation.objects.create(name="Beta Attachments", slug="beta-attachments")
    owner, owner_role = create_account(alpha, "owner-attachments@alpha.test")
    dispatcher, dispatcher_role = create_account(
        alpha, "dispatcher-attachments@alpha.test", OrganisationUserRole.DISPATCHER
    )
    technician, technician_role = create_account(
        alpha, "tech-attachments@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    other_technician, other_technician_role = create_account(
        alpha, "other-tech-attachments@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    beta_owner, beta_owner_role = create_account(beta, "owner-attachments@beta.test")
    order = WorkOrder.objects.create(
        organisation=alpha,
        creator=owner_role,
        assigned_technician=technician_role,
        reference_number="WO-ATT-0001",
        title="Attachment test",
        site_name="Test site",
    )
    return locals()


def upload(client, order, content=PDF_BYTES, name="report.pdf", content_type="application/pdf"):
    return client.post(
        f"/api/v1/work-orders/{order.id}/attachments",
        {"file": SimpleUploadedFile(name, content, content_type=content_type)},
        format="multipart",
    )


@pytest.mark.django_db
def test_upload_detects_content_tracks_quota_and_hides_storage_key(attachment_accounts):
    accounts = attachment_accounts
    response = upload(
        authenticated_client(accounts["dispatcher"]),
        accounts["order"],
        name="..\\..\\site report.pdf",
    )

    assert response.status_code == 201
    assert response.data["data"]["fileName"] == "site report.pdf"
    assert "storage" not in str(response.data).lower()
    attachment = Attachment.objects.get()
    assert attachment.storage_key.startswith("attachments/")
    assert "site report" not in attachment.storage_key
    accounts["alpha"].refresh_from_db()
    assert accounts["alpha"].storage_used_bytes == len(PDF_BYTES)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "content", "content_type"),
    [
        ("empty.pdf", b"", "application/pdf"),
        ("spoofed.pdf", PNG_BYTES, "application/pdf"),
        ("script.jpg", b"<script>alert(1)</script>", "image/jpeg"),
        ("wrong.txt", PDF_BYTES, "application/pdf"),
    ],
)
def test_upload_rejects_empty_spoofed_and_unsupported_files(
    attachment_accounts, name, content, content_type
):
    response = upload(
        authenticated_client(attachment_accounts["owner"]),
        attachment_accounts["order"],
        content=content,
        name=name,
        content_type=content_type,
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert Attachment.objects.count() == 0


@pytest.mark.django_db
def test_upload_rejects_file_over_configured_limit(attachment_accounts, settings):
    settings.ATTACHMENT_MAX_BYTES = 16
    response = upload(
        authenticated_client(attachment_accounts["owner"]),
        attachment_accounts["order"],
    )

    assert response.status_code == 400
    assert Attachment.objects.count() == 0


@pytest.mark.django_db
def test_quota_boundary_returns_stable_conflict(attachment_accounts):
    accounts = attachment_accounts
    accounts["alpha"].storage_limit_bytes = len(PDF_BYTES) - 1
    accounts["alpha"].save(update_fields=("storage_limit_bytes", "updated_at"))

    response = upload(authenticated_client(accounts["owner"]), accounts["order"])

    assert response.status_code == 409
    assert response.data["error"]["code"] == "STORAGE_QUOTA_EXCEEDED"
    accounts["alpha"].refresh_from_db()
    assert accounts["alpha"].storage_used_bytes == 0
    assert Attachment.objects.count() == 0


@pytest.mark.django_db
def test_assigned_technician_can_upload_but_other_users_cannot_see_order(
    attachment_accounts,
):
    accounts = attachment_accounts
    assigned = upload(authenticated_client(accounts["technician"]), accounts["order"])
    other = upload(authenticated_client(accounts["other_technician"]), accounts["order"])
    cross_tenant = upload(authenticated_client(accounts["beta_owner"]), accounts["order"])

    assert assigned.status_code == 201
    assert other.status_code == cross_tenant.status_code == 404
    assert Attachment.objects.count() == 1


@pytest.mark.django_db
def test_protected_download_and_list_are_tenant_and_assignment_scoped(attachment_accounts):
    accounts = attachment_accounts
    owner_client = authenticated_client(accounts["owner"])
    created = upload(owner_client, accounts["order"])
    attachment_id = created.data["data"]["id"]
    url = f"/api/v1/work-orders/{accounts['order'].id}/attachments/{attachment_id}"

    listing = owner_client.get(f"/api/v1/work-orders/{accounts['order'].id}/attachments")
    download = authenticated_client(accounts["technician"]).get(url)
    denied = authenticated_client(accounts["other_technician"]).get(url)
    cross_tenant = authenticated_client(accounts["beta_owner"]).get(url)

    assert listing.status_code == 200
    assert listing.data["data"][0]["id"] == attachment_id
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == PDF_BYTES
    assert download["X-Content-Type-Options"] == "nosniff"
    assert denied.status_code == cross_tenant.status_code == 404


@pytest.mark.django_db
def test_dispatcher_delete_restores_quota_and_removes_access(
    attachment_accounts, django_capture_on_commit_callbacks
):
    accounts = attachment_accounts
    client = authenticated_client(accounts["dispatcher"])
    created = upload(client, accounts["order"])
    attachment_id = created.data["data"]["id"]
    url = f"/api/v1/work-orders/{accounts['order'].id}/attachments/{attachment_id}"

    with django_capture_on_commit_callbacks(execute=True):
        deleted = client.delete(url)

    assert deleted.status_code == 204
    accounts["alpha"].refresh_from_db()
    assert accounts["alpha"].storage_used_bytes == 0
    assert Attachment.objects.count() == 0
    assert Attachment.all_objects.filter(pk=attachment_id, deleted_at__isnull=False).exists()
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_technician_cannot_delete_attachment(attachment_accounts):
    accounts = attachment_accounts
    created = upload(authenticated_client(accounts["owner"]), accounts["order"])
    url = (
        f"/api/v1/work-orders/{accounts['order'].id}/attachments/"
        f"{created.data['data']['id']}"
    )

    response = authenticated_client(accounts["technician"]).delete(url)

    assert response.status_code == 403
    assert Attachment.objects.count() == 1


@pytest.mark.django_db
def test_storage_is_cleaned_and_database_rolls_back_when_metadata_save_fails(
    attachment_accounts, monkeypatch
):
    accounts = attachment_accounts

    def fail_save(*args, **kwargs):
        raise RuntimeError("injected metadata failure")

    monkeypatch.setattr(Attachment, "save", fail_save)
    response = upload(authenticated_client(accounts["owner"]), accounts["order"])

    assert response.status_code == 500
    accounts["alpha"].refresh_from_db()
    assert accounts["alpha"].storage_used_bytes == 0
    assert Attachment.objects.count() == 0
    media_files = [path for path in accounts["settings"].MEDIA_ROOT.rglob("*") if path.is_file()]
    assert media_files == []


@pytest.mark.django_db(transaction=True)
def test_concurrent_uploads_cannot_exceed_organisation_quota(
    attachment_accounts,
):
    accounts = attachment_accounts
    accounts["alpha"].storage_limit_bytes = len(PDF_BYTES)
    accounts["alpha"].save(update_fields=("storage_limit_bytes", "updated_at"))
    token = str(RefreshToken.for_user(accounts["owner"]).access_token)
    barrier = Barrier(2)

    def submit(index):
        close_old_connections()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        barrier.wait()
        response = upload(client, accounts["order"], name=f"report-{index}.pdf")
        close_old_connections()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(submit, range(2)))

    assert statuses == [201, 409]
    accounts["alpha"].refresh_from_db()
    assert accounts["alpha"].storage_used_bytes == len(PDF_BYTES)
    assert Attachment.objects.count() == 1
