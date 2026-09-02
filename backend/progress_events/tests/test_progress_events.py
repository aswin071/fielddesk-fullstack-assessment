from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from progress_events.models import ProgressEvent
from workorders.models import WorkOrder, WorkOrderStatus


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def event_accounts(db):
    alpha = Organisation.objects.create(name="Alpha Field", slug="alpha-field")
    beta = Organisation.objects.create(name="Beta Field", slug="beta-field")
    owner, owner_role = create_account(alpha, "owner-events@alpha.test")
    technician, technician_role = create_account(
        alpha, "tech-events@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    other_technician, other_technician_role = create_account(
        alpha, "other-tech-events@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    beta_technician, beta_technician_role = create_account(
        beta, "tech-events@beta.test", OrganisationUserRole.TECHNICIAN
    )
    return locals()


def create_scheduled_order(accounts):
    start = timezone.now() + timedelta(hours=1)
    return WorkOrder.objects.create(
        organisation=accounts["alpha"],
        creator=accounts["owner_role"],
        assigned_technician=accounts["technician_role"],
        reference_number="WO-EVENT-0001",
        title="Service cooling plant",
        site_name="North plant",
        status=WorkOrderStatus.SCHEDULED,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=1),
    )


def event_payload(order, event_id="evt-10001", **overrides):
    payload = {
        "eventId": event_id,
        "workOrderId": str(order.id),
        "type": "status_changed",
        "occurredAt": timezone.now().isoformat(),
        "payload": {"status": WorkOrderStatus.IN_PROGRESS},
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_status_event_updates_order_and_records_immutable_input(event_accounts):
    order = create_scheduled_order(event_accounts)
    payload = event_payload(order)

    response = authenticated_client(event_accounts["technician"]).post(
        "/api/v1/progress-events", payload, format="json"
    )

    assert response.status_code == 201
    assert response.data["meta"]["idempotentReplay"] is False
    order.refresh_from_db()
    assert order.status == WorkOrderStatus.IN_PROGRESS
    event = ProgressEvent.objects.get()
    assert event.original_event == payload
    assert event.result == response.data["data"]


@pytest.mark.django_db
def test_exact_duplicate_returns_consistent_idempotent_response(event_accounts):
    order = create_scheduled_order(event_accounts)
    payload = event_payload(order)
    client = authenticated_client(event_accounts["technician"])

    first = client.post("/api/v1/progress-events", payload, format="json")
    replay = client.post("/api/v1/progress-events", payload, format="json")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.data["meta"]["idempotentReplay"] is True
    assert replay.data["data"] == first.data["data"]
    assert ProgressEvent.objects.count() == 1


@pytest.mark.django_db
def test_reusing_event_id_for_different_payload_returns_conflict(event_accounts):
    order = create_scheduled_order(event_accounts)
    client = authenticated_client(event_accounts["technician"])
    first = event_payload(order)
    changed = event_payload(order, payload={"status": WorkOrderStatus.COMPLETED})

    assert client.post("/api/v1/progress-events", first, format="json").status_code == 201
    response = client.post("/api/v1/progress-events", changed, format="json")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert ProgressEvent.objects.count() == 1


@pytest.mark.django_db
def test_event_is_hidden_from_wrong_technician_and_wrong_organisation(event_accounts):
    order = create_scheduled_order(event_accounts)
    payload = event_payload(order)

    other = authenticated_client(event_accounts["other_technician"]).post(
        "/api/v1/progress-events", payload, format="json"
    )
    cross_tenant = authenticated_client(event_accounts["beta_technician"]).post(
        "/api/v1/progress-events", payload, format="json"
    )
    owner = authenticated_client(event_accounts["owner"]).post(
        "/api/v1/progress-events", payload, format="json"
    )

    assert other.status_code == cross_tenant.status_code == 404
    assert owner.status_code == 403
    assert ProgressEvent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change",
    [
        {"extra": "rejected"},
        {"type": "unknown"},
        {"payload": {"unexpected": True}},
        {"payload": {"status": "scheduled"}},
        # Keep a wide margin so test-suite runtime cannot move this inside the
        # configured five-minute future tolerance.
        {"occurredAt": (timezone.now() + timedelta(hours=1)).isoformat()},
        {"occurredAt": (timezone.now() - timedelta(days=31)).isoformat()},
    ],
)
def test_event_contract_rejects_invalid_inputs(event_accounts, change):
    order = create_scheduled_order(event_accounts)
    response = authenticated_client(event_accounts["technician"]).post(
        "/api/v1/progress-events", event_payload(order, **change), format="json"
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert ProgressEvent.objects.count() == 0


@pytest.mark.django_db
def test_note_event_does_not_change_work_order_status(event_accounts):
    order = create_scheduled_order(event_accounts)
    payload = event_payload(
        order,
        type="note_added",
        payload={"note": "Replacement part ordered."},
    )

    response = authenticated_client(event_accounts["technician"]).post(
        "/api/v1/progress-events", payload, format="json"
    )

    assert response.status_code == 201
    order.refresh_from_db()
    assert order.status == WorkOrderStatus.SCHEDULED


@pytest.mark.django_db
def test_transaction_rolls_back_work_order_when_event_insert_fails(event_accounts, monkeypatch):
    order = create_scheduled_order(event_accounts)

    def fail_save(*args, **kwargs):
        raise RuntimeError("injected storage failure")

    monkeypatch.setattr(ProgressEvent, "save", fail_save)
    response = authenticated_client(event_accounts["technician"]).post(
        "/api/v1/progress-events", event_payload(order), format="json"
    )

    assert response.status_code == 500
    order.refresh_from_db()
    assert order.status == WorkOrderStatus.SCHEDULED
    assert ProgressEvent.objects.count() == 0


@pytest.mark.django_db
def test_persisted_progress_event_cannot_be_changed_or_deleted(event_accounts):
    order = create_scheduled_order(event_accounts)
    authenticated_client(event_accounts["technician"]).post(
        "/api/v1/progress-events", event_payload(order), format="json"
    )
    event = ProgressEvent.objects.get()

    event.payload = {"status": WorkOrderStatus.COMPLETED}
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_submissions_create_one_event(event_accounts):
    order = create_scheduled_order(event_accounts)
    payload = event_payload(order)
    token = str(RefreshToken.for_user(event_accounts["technician"]).access_token)
    barrier = Barrier(2)

    def submit():
        close_old_connections()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        barrier.wait()
        response = client.post("/api/v1/progress-events", payload, format="json")
        close_old_connections()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: submit(), range(2)))

    assert statuses == [200, 201]
    assert ProgressEvent.objects.count() == 1
    order.refresh_from_db()
    assert order.status == WorkOrderStatus.IN_PROGRESS
