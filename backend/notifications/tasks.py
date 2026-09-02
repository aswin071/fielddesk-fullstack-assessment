import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit
from notifications.models import (
    NotificationAttempt,
    NotificationAttemptOutcome,
    NotificationDelivery,
    NotificationDeliveryStatus,
)
from notifications.provider import (
    PermanentProviderError,
    TemporaryProviderError,
    get_notification_provider,
)
from realtime.services import publish_realtime_after_commit

logger = logging.getLogger("fielddesk.notifications")
TERMINAL_STATUSES = {
    NotificationDeliveryStatus.DELIVERED,
    NotificationDeliveryStatus.PERMANENTLY_FAILED,
}


def _diagnostic(error):
    return str(error)[:500]


def _record_attempt(*, delivery, number, outcome, diagnostic="", provider_reference=""):
    attempt = NotificationAttempt(
        organisation=delivery.organisation,
        delivery=delivery,
        attempt_number=number,
        outcome=outcome,
        diagnostic=diagnostic,
        provider_reference=provider_reference,
    )
    attempt.full_clean()
    attempt.save()


@shared_task(bind=True, acks_late=True)
def deliver_assignment_notification(self, delivery_id):
    retry_error = None
    with transaction.atomic():
        delivery = (
            NotificationDelivery.objects.select_for_update()
            .select_related("organisation", "technician__user", "work_order")
            .get(pk=delivery_id)
        )
        if delivery.status in TERMINAL_STATUSES:
            return {"status": delivery.status, "attemptCount": delivery.attempt_count}

        attempt_number = delivery.attempt_count + 1
        provider = get_notification_provider()
        try:
            result = provider.send_assignment(
                delivery=delivery,
                attempt_number=attempt_number,
            )
        except PermanentProviderError as exc:
            diagnostic = _diagnostic(exc)
            _record_attempt(
                delivery=delivery,
                number=attempt_number,
                outcome=NotificationAttemptOutcome.PERMANENT_FAILURE,
                diagnostic=diagnostic,
            )
            delivery.status = NotificationDeliveryStatus.PERMANENTLY_FAILED
            delivery.attempt_count = attempt_number
            delivery.last_error = diagnostic
            delivery.finished_at = timezone.now()
        except TemporaryProviderError as exc:
            diagnostic = _diagnostic(exc)
            _record_attempt(
                delivery=delivery,
                number=attempt_number,
                outcome=NotificationAttemptOutcome.TEMPORARY_FAILURE,
                diagnostic=diagnostic,
            )
            delivery.attempt_count = attempt_number
            delivery.last_error = diagnostic
            if self.request.retries >= settings.NOTIFICATION_MAX_RETRIES:
                delivery.status = NotificationDeliveryStatus.PERMANENTLY_FAILED
                delivery.finished_at = timezone.now()
            else:
                delivery.status = NotificationDeliveryStatus.RETRYING
                retry_error = exc
        else:
            _record_attempt(
                delivery=delivery,
                number=attempt_number,
                outcome=NotificationAttemptOutcome.DELIVERED,
                provider_reference=result.reference,
            )
            delivery.status = NotificationDeliveryStatus.DELIVERED
            delivery.attempt_count = attempt_number
            delivery.last_error = ""
            delivery.delivered_at = timezone.now()
            delivery.finished_at = delivery.delivered_at

        delivery.save(
            update_fields=(
                "status",
                "attempt_count",
                "last_error",
                "delivered_at",
                "finished_at",
                "updated_at",
            )
        )
        attempt = delivery.attempts.get(attempt_number=attempt_number)
        record_audit(
            organisation=delivery.organisation,
            actor=None,
            action=f"notification.{attempt.outcome}",
            target_type="NotificationDelivery",
            target_id=delivery.id,
            related_work_order=delivery.work_order,
            before={"status": "queued" if attempt_number == 1 else "retrying"},
            after={"status": delivery.status},
            metadata={
                "system": "celery-worker",
                "attemptNumber": attempt_number,
                "outcome": attempt.outcome,
            },
        )
        publish_realtime_after_commit(
            organisation_id=delivery.organisation_id,
            event_type="notification.updated",
            target_id=delivery.work_order_id,
            changes={"deliveryStatus": delivery.status},
        )
        status_value = delivery.status

    logger.info(
        "notification_attempt_finished",
        extra={
            "event": "notification_attempt_finished",
            "delivery_id": str(delivery_id),
            "attempt_number": attempt_number,
            "outcome": status_value,
        },
    )
    if retry_error is not None:
        countdown = settings.NOTIFICATION_RETRY_BASE_SECONDS * (2**self.request.retries)
        raise self.retry(
            exc=retry_error,
            countdown=countdown,
            max_retries=settings.NOTIFICATION_MAX_RETRIES,
        )
    return {"status": status_value, "attemptCount": attempt_number}
