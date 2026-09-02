import logging
import uuid

from django.db import transaction

from notifications.models import NotificationDelivery

logger = logging.getLogger("fielddesk.notifications")


def create_assignment_delivery(*, work_order):
    revision = work_order.assignment_revision
    deduplication_key = f"assignment:{work_order.id}:{revision}"
    delivery, _ = NotificationDelivery.objects.get_or_create(
        work_order=work_order,
        assignment_revision=revision,
        defaults={
            "organisation": work_order.organisation,
            "technician": work_order.assigned_technician,
            "deduplication_key": deduplication_key,
            "provider_idempotency_key": uuid.uuid4(),
        },
    )
    transaction.on_commit(lambda: enqueue_notification_delivery(delivery.id))
    return delivery


def enqueue_notification_delivery(delivery_id):
    from notifications.tasks import deliver_assignment_notification

    try:
        deliver_assignment_notification.delay(str(delivery_id))
    except Exception:
        logger.exception(
            "notification_enqueue_failed",
            extra={
                "event": "notification_enqueue_failed",
                "delivery_id": str(delivery_id),
            },
        )
