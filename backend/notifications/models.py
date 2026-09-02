from django.core.exceptions import ValidationError
from django.db import models

from common.models import (
    ImmutableModel,
    OrganisationBaseModel,
    OrganisationManager,
    OrganisationOwnedModel,
    TimeStampedModel,
    UUIDModel,
)
from organisations.models import OrganisationUser
from workorders.models import WorkOrder


class NotificationDeliveryStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RETRYING = "retrying", "Retrying"
    DELIVERED = "delivered", "Delivered"
    PERMANENTLY_FAILED = "permanently_failed", "Permanently failed"


class NotificationAttemptOutcome(models.TextChoices):
    DELIVERED = "delivered", "Delivered"
    TEMPORARY_FAILURE = "temporary_failure", "Temporary failure"
    PERMANENT_FAILURE = "permanent_failure", "Permanent failure"


class NotificationDelivery(OrganisationBaseModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
    )
    technician = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
    )
    assignment_revision = models.PositiveIntegerField()
    deduplication_key = models.CharField(max_length=160, unique=True)
    provider_idempotency_key = models.UUIDField(unique=True)
    status = models.CharField(
        max_length=30,
        choices=NotificationDeliveryStatus.choices,
        default=NotificationDeliveryStatus.QUEUED,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("work_order", "assignment_revision"),
                name="unique_notification_per_assignment_revision",
            )
        ]
        indexes = [
            models.Index(fields=("organisation", "status", "created_at")),
            models.Index(fields=("organisation", "technician", "created_at")),
        ]

    def clean(self):
        errors = {}
        if self.work_order_id and self.work_order.organisation_id != self.organisation_id:
            errors["work_order"] = "Work order must belong to the delivery organisation."
        if self.technician_id and self.technician.organisation_id != self.organisation_id:
            errors["technician"] = "Technician must belong to the delivery organisation."
        if errors:
            raise ValidationError(errors)


class NotificationAttempt(
    UUIDModel,
    TimeStampedModel,
    OrganisationOwnedModel,
    ImmutableModel,
):
    delivery = models.ForeignKey(
        NotificationDelivery,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    attempt_number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=30, choices=NotificationAttemptOutcome.choices)
    diagnostic = models.CharField(max_length=500, blank=True)
    provider_reference = models.CharField(max_length=200, blank=True)

    objects = OrganisationManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("attempt_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("delivery", "attempt_number"),
                name="unique_notification_attempt_number",
            )
        ]

    def clean(self):
        if self.delivery_id and self.delivery.organisation_id != self.organisation_id:
            raise ValidationError(
                {"delivery": "Delivery must belong to the attempt organisation."}
            )
