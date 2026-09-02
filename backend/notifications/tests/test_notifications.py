import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from celery.exceptions import Retry
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from notifications.models import (
    NotificationAttempt,
    NotificationAttemptOutcome,
    NotificationDelivery,
    NotificationDeliveryStatus,
)
from notifications.services import create_assignment_delivery, enqueue_notification_delivery
from notifications.tasks import deliver_assignment_notification
from organisations.models import Organisation, OrganisationUserRole
from workorders.models import WorkOrder, WorkOrderStatus


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def notification_accounts(db):
    organisation = Organisation.objects.create(name="Notify Services", slug="notify-services")
    dispatcher, dispatcher_role = create_account(
        organisation,
        "dispatcher-notify@example.test",
        OrganisationUserRole.DISPATCHER,
    )
    technician, technician_role = create_account(
        organisation,
        "technician-notify@example.test",
        OrganisationUserRole.TECHNICIAN,
    )
    order = WorkOrder.objects.create(
        organisation=organisation,
        creator=dispatcher_role,
        reference_number="WO-NOTIFY-0001",
        title="Notify technician",
        site_name="Main site",
    )
    return locals()


def assign(client, accounts, start=None):
    start = start or timezone.now() + timedelta(hours=2)
    return client.post(
        f"/api/v1/work-orders/{accounts['order'].id}/assign",
        {
            "technicianId": str(accounts["technician_role"].id),
            "scheduledStart": start.isoformat(),
            "scheduledEnd": (start + timedelta(hours=1)).isoformat(),
        },
        format="json",
    )


def delivery_for(accounts, revision=1):
    accounts["order"].assigned_technician = accounts["technician_role"]
    accounts["order"].assignment_revision = revision
    accounts["order"].save(
        update_fields=("assigned_technician", "assignment_revision", "updated_at")
    )
    return NotificationDelivery.objects.create(
        organisation=accounts["organisation"],
        work_order=accounts["order"],
        technician=accounts["technician_role"],
        assignment_revision=revision,
        deduplication_key=f"assignment:{accounts['order'].id}:{revision}",
        provider_idempotency_key=uuid.uuid4(),
    )


@pytest.mark.django_db
def test_assignment_creates_delivery_and_enqueues_only_after_commit(
    notification_accounts,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    enqueued = []
    monkeypatch.setattr(
        "notifications.services.enqueue_notification_delivery",
        lambda delivery_id: enqueued.append(delivery_id),
    )

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        response = assign(
            authenticated_client(notification_accounts["dispatcher"]),
            notification_accounts,
        )

    assert response.status_code == 200
    delivery = NotificationDelivery.objects.get()
    assert delivery.status == NotificationDeliveryStatus.QUEUED
    assert delivery.assignment_revision == 1
    assert enqueued == []
    assert callbacks
    for callback in callbacks:
        callback()
    assert enqueued == [delivery.id]


@pytest.mark.django_db
def test_each_assignment_revision_has_one_deduplicated_delivery(notification_accounts):
    first = delivery_for(notification_accounts)
    duplicate = create_assignment_delivery(work_order=notification_accounts["order"])

    assert duplicate.id == first.id
    assert NotificationDelivery.objects.count() == 1
    assert str(notification_accounts["order"].id) in first.deduplication_key


@pytest.mark.django_db
def test_success_records_attempt_and_terminal_outcome(notification_accounts, settings):
    settings.NOTIFICATION_PROVIDER_MODE = "success"
    delivery = delivery_for(notification_accounts)

    result = deliver_assignment_notification.run(str(delivery.id))

    delivery.refresh_from_db()
    attempt = NotificationAttempt.objects.get()
    assert result == {"status": "delivered", "attemptCount": 1}
    assert delivery.status == NotificationDeliveryStatus.DELIVERED
    assert delivery.delivered_at is not None
    assert attempt.outcome == NotificationAttemptOutcome.DELIVERED
    assert str(delivery.provider_idempotency_key) in attempt.provider_reference


@pytest.mark.django_db
def test_temporary_failure_retries_then_succeeds(
    notification_accounts, settings, monkeypatch
):
    settings.NOTIFICATION_PROVIDER_MODE = "temporary_then_success"
    settings.NOTIFICATION_PROVIDER_TEMPORARY_FAILURES = 1
    settings.NOTIFICATION_MAX_RETRIES = 3
    settings.NOTIFICATION_RETRY_BASE_SECONDS = 0
    delivery = delivery_for(notification_accounts)
    retry_requests = []

    def request_retry(**kwargs):
        retry_requests.append(kwargs)
        raise Retry()

    monkeypatch.setattr(deliver_assignment_notification, "retry", request_retry)

    with pytest.raises(Retry):
        deliver_assignment_notification.run(str(delivery.id))
    delivery.refresh_from_db()
    assert delivery.status == NotificationDeliveryStatus.RETRYING
    assert delivery.attempt_count == 1
    assert retry_requests[0]["countdown"] == 0

    result = deliver_assignment_notification.run(str(delivery.id))

    delivery.refresh_from_db()
    assert result["status"] == NotificationDeliveryStatus.DELIVERED
    assert delivery.attempt_count == 2
    assert list(delivery.attempts.values_list("outcome", flat=True)) == [
        NotificationAttemptOutcome.TEMPORARY_FAILURE,
        NotificationAttemptOutcome.DELIVERED,
    ]


@pytest.mark.django_db
def test_temporary_retry_exhaustion_is_final(notification_accounts, settings):
    settings.NOTIFICATION_PROVIDER_MODE = "temporary_failure"
    settings.NOTIFICATION_MAX_RETRIES = 0
    delivery = delivery_for(notification_accounts)

    result = deliver_assignment_notification.run(str(delivery.id))

    delivery.refresh_from_db()
    assert result["status"] == NotificationDeliveryStatus.PERMANENTLY_FAILED
    assert delivery.finished_at is not None
    assert delivery.attempts.get().outcome == NotificationAttemptOutcome.TEMPORARY_FAILURE


@pytest.mark.django_db
def test_permanent_failure_never_requests_retry(notification_accounts, settings, monkeypatch):
    settings.NOTIFICATION_PROVIDER_MODE = "permanent_failure"
    delivery = delivery_for(notification_accounts)
    retry_calls = []
    monkeypatch.setattr(
        deliver_assignment_notification,
        "retry",
        lambda **kwargs: retry_calls.append(kwargs),
    )

    result = deliver_assignment_notification.run(str(delivery.id))

    delivery.refresh_from_db()
    assert result["status"] == NotificationDeliveryStatus.PERMANENTLY_FAILED
    assert retry_calls == []
    assert delivery.attempts.get().outcome == NotificationAttemptOutcome.PERMANENT_FAILURE


@pytest.mark.django_db
def test_duplicate_task_delivery_does_not_call_provider_twice(
    notification_accounts, settings
):
    settings.NOTIFICATION_PROVIDER_MODE = "success"
    delivery = delivery_for(notification_accounts)

    first = deliver_assignment_notification.run(str(delivery.id))
    duplicate = deliver_assignment_notification.run(str(delivery.id))

    assert first == duplicate
    assert NotificationAttempt.objects.count() == 1


@pytest.mark.django_db
def test_attempt_history_is_immutable(notification_accounts, settings):
    settings.NOTIFICATION_PROVIDER_MODE = "success"
    delivery = delivery_for(notification_accounts)
    deliver_assignment_notification.run(str(delivery.id))
    attempt = NotificationAttempt.objects.get()

    attempt.diagnostic = "tampered"
    with pytest.raises(ValidationError):
        attempt.save()
    with pytest.raises(ValidationError):
        attempt.delete()


@pytest.mark.django_db
def test_enqueue_failure_is_logged_without_changing_durable_delivery(
    notification_accounts, monkeypatch
):
    delivery = delivery_for(notification_accounts)
    logged_events = []

    def broker_failure(*args, **kwargs):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(deliver_assignment_notification, "delay", broker_failure)
    monkeypatch.setattr(
        "notifications.services.logger.exception",
        lambda message, **kwargs: logged_events.append(message),
    )
    enqueue_notification_delivery(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDeliveryStatus.QUEUED
    assert logged_events == ["notification_enqueue_failed"]


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_tasks_produce_one_provider_attempt(
    notification_accounts, settings
):
    settings.NOTIFICATION_PROVIDER_MODE = "success"
    delivery = delivery_for(notification_accounts)

    def run_task(_):
        close_old_connections()
        result = deliver_assignment_notification.run(str(delivery.id))
        close_old_connections()
        return result["status"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run_task, range(2)))

    assert results == [NotificationDeliveryStatus.DELIVERED] * 2
    assert NotificationAttempt.objects.count() == 1
    delivery.refresh_from_db()
    assert delivery.attempt_count == 1


@pytest.mark.django_db
def test_conflicting_assignment_creates_no_delivery(notification_accounts):
    accounts = notification_accounts
    start = timezone.now() + timedelta(hours=3)
    other_order = WorkOrder.objects.create(
        organisation=accounts["organisation"],
        creator=accounts["dispatcher_role"],
        assigned_technician=accounts["technician_role"],
        reference_number="WO-NOTIFY-EXISTING",
        title="Existing assignment",
        site_name="Main site",
        status=WorkOrderStatus.SCHEDULED,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=1),
    )

    response = assign(
        authenticated_client(accounts["dispatcher"]),
        accounts,
        start=start + timedelta(minutes=10),
    )

    assert response.status_code == 409
    assert other_order.assigned_technician_id == accounts["technician_role"].id
    assert NotificationDelivery.objects.count() == 0
