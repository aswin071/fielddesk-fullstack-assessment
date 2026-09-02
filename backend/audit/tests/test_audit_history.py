from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditEntry
from authentication.tests.test_authentication import create_account
from notifications.models import NotificationDelivery
from notifications.tasks import deliver_assignment_notification
from organisations.models import Organisation, OrganisationUserRole
from workorders.models import WorkOrder

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def audit_accounts(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.NOTIFICATION_PROVIDER_MODE = "success"
    alpha = Organisation.objects.create(name="Audit Alpha", slug="audit-alpha")
    beta = Organisation.objects.create(name="Audit Beta", slug="audit-beta")
    owner, owner_role = create_account(alpha, "owner-audit@alpha.test")
    technician, technician_role = create_account(
        alpha, "technician-audit@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    other_technician, other_technician_role = create_account(
        alpha, "other-technician-audit@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    beta_owner, beta_owner_role = create_account(beta, "owner-audit@beta.test")
    return locals()


def create_order(client, correlation_id="audit-correlation-1"):
    return client.post(
        "/api/v1/work-orders",
        {"title": "Audit boiler service", "siteName": "Plant room"},
        format="json",
        HTTP_X_CORRELATION_ID=correlation_id,
    )


@pytest.mark.django_db
def test_work_order_creation_records_actor_snapshot_and_correlation_id(audit_accounts):
    response = create_order(authenticated_client(audit_accounts["owner"]))

    assert response.status_code == 201
    entry = AuditEntry.objects.get()
    assert entry.organisation == audit_accounts["alpha"]
    assert entry.actor == audit_accounts["owner_role"]
    assert entry.action == "work_order.created"
    assert entry.target_type == "WorkOrder"
    assert entry.target_id == WorkOrder.objects.get().id
    assert entry.after["title"] == "Audit boiler service"
    assert entry.before == {}
    assert entry.correlation_id == "audit-correlation-1"


@pytest.mark.django_db
def test_complete_work_order_activity_records_required_actions(audit_accounts):
    accounts = audit_accounts
    owner_client = authenticated_client(accounts["owner"])
    created = create_order(owner_client)
    order_id = created.data["data"]["id"]
    start = timezone.now() + timedelta(hours=2)
    assigned = owner_client.post(
        f"/api/v1/work-orders/{order_id}/assign",
        {
            "technicianId": str(accounts["technician_role"].id),
            "scheduledStart": start.isoformat(),
            "scheduledEnd": (start + timedelta(hours=1)).isoformat(),
        },
        format="json",
    )
    assert assigned.status_code == 200

    progressed = authenticated_client(accounts["technician"]).post(
        "/api/v1/progress-events",
        {
            "eventId": "evt-audit-1",
            "workOrderId": order_id,
            "type": "status_changed",
            "occurredAt": timezone.now().isoformat(),
            "payload": {"status": "in_progress", "note": "Started"},
        },
        format="json",
    )
    assert progressed.status_code == 201

    attachment = owner_client.post(
        f"/api/v1/work-orders/{order_id}/attachments",
        {
            "file": SimpleUploadedFile(
                "service.pdf",
                PDF_BYTES,
                content_type="application/pdf",
            )
        },
        format="multipart",
    )
    assert attachment.status_code == 201
    attachment_id = attachment.data["data"]["id"]
    assert owner_client.delete(
        f"/api/v1/work-orders/{order_id}/attachments/{attachment_id}"
    ).status_code == 204

    delivery = NotificationDelivery.objects.get()
    deliver_assignment_notification.run(str(delivery.id))

    activity = owner_client.get(f"/api/v1/work-orders/{order_id}/activity?pageSize=20")

    assert activity.status_code == 200
    actions = {item["action"] for item in activity.data["data"]}
    assert actions == {
        "work_order.created",
        "work_order.assigned",
        "progress_event.accepted",
        "attachment.added",
        "attachment.deleted",
        "notification.delivered",
    }
    notification_entry = next(
        item for item in activity.data["data"] if item["action"] == "notification.delivered"
    )
    assert notification_entry["actor"] is None
    assert notification_entry["metadata"]["system"] == "celery-worker"
    assert "diagnostic" not in notification_entry["metadata"]


@pytest.mark.django_db
def test_work_order_edit_records_before_after_and_changed_fields(audit_accounts):
    client = authenticated_client(audit_accounts["owner"])
    order_id = create_order(client).data["data"]["id"]

    response = client.patch(
        f"/api/v1/work-orders/{order_id}",
        {"title": "Updated boiler service", "priority": "high"},
        format="json",
    )

    assert response.status_code == 200
    entry = AuditEntry.objects.get(action="work_order.updated")
    assert entry.before["title"] == "Audit boiler service"
    assert entry.after["title"] == "Updated boiler service"
    assert set(entry.metadata["changedFields"]) == {"title", "priority"}


@pytest.mark.django_db
def test_user_create_and_role_status_update_are_audited_without_password(audit_accounts):
    client = authenticated_client(audit_accounts["owner"])
    created = client.post(
        "/api/v1/users/",
        {
            "email": "new-audit-user@example.test",
            "firstName": "Audit",
            "lastName": "User",
            "password": "StrongAudit!2026",
            "role": "technician",
        },
        format="json",
    )
    assert created.status_code == 201
    user_id = created.data["data"]["id"]

    updated = client.patch(
        f"/api/v1/users/{user_id}",
        {"role": "dispatcher", "isActive": False},
        format="json",
    )

    assert updated.status_code == 200
    entries = list(AuditEntry.objects.order_by("created_at"))
    assert [entry.action for entry in entries] == ["user.created", "user.updated"]
    assert entries[1].before["role"] == "technician"
    assert entries[1].after["role"] == "dispatcher"
    assert set(entries[1].metadata["changedFields"]) == {"role", "isActive"}
    assert "password" not in str(entries).lower()


@pytest.mark.django_db
def test_activity_is_hidden_cross_tenant_and_from_unassigned_technician(audit_accounts):
    accounts = audit_accounts
    order_id = create_order(authenticated_client(accounts["owner"])).data["data"]["id"]
    url = f"/api/v1/work-orders/{order_id}/activity"

    cross_tenant = authenticated_client(accounts["beta_owner"]).get(url)
    unassigned = authenticated_client(accounts["other_technician"]).get(url)

    assert cross_tenant.status_code == unassigned.status_code == 404


@pytest.mark.django_db
def test_activity_has_no_mutation_endpoint_and_entries_are_immutable(audit_accounts):
    client = authenticated_client(audit_accounts["owner"])
    order_id = create_order(client).data["data"]["id"]
    url = f"/api/v1/work-orders/{order_id}/activity"
    entry = AuditEntry.objects.get()

    assert client.post(url, {}, format="json").status_code == 405
    assert client.patch(url, {}, format="json").status_code == 405
    assert client.delete(url).status_code == 405
    entry.metadata = {"tampered": True}
    with pytest.raises(ValidationError):
        entry.save()
    with pytest.raises(ValidationError):
        entry.delete()


@pytest.mark.django_db
def test_business_failure_after_audit_write_rolls_back_both(audit_accounts, monkeypatch):
    def fail_after_audit(**kwargs):
        raise RuntimeError("injected post-audit failure")

    monkeypatch.setattr(
        "workorders.services.publish_realtime_after_commit",
        fail_after_audit,
    )

    response = create_order(authenticated_client(audit_accounts["owner"]))

    assert response.status_code == 500
    assert WorkOrder.objects.count() == 0
    assert AuditEntry.objects.count() == 0
