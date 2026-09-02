from django.core.exceptions import ValidationError
from django.db import models

from common.models import (
    ImmutableModel,
    OrganisationManager,
    OrganisationOwnedModel,
    TimeStampedModel,
    UUIDModel,
)
from organisations.models import OrganisationUser
from workorders.models import WorkOrder


class ProgressEventType(models.TextChoices):
    STATUS_CHANGED = "status_changed", "Status changed"
    NOTE_ADDED = "note_added", "Note added"


class ProgressEvent(
    UUIDModel,
    TimeStampedModel,
    OrganisationOwnedModel,
    ImmutableModel,
):
    event_id = models.CharField(max_length=100)
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="progress_events",
    )
    actor = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="submitted_progress_events",
    )
    event_type = models.CharField(max_length=30, choices=ProgressEventType.choices)
    occurred_at = models.DateTimeField(db_index=True)
    payload = models.JSONField()
    original_event = models.JSONField()
    request_hash = models.CharField(max_length=64)
    result = models.JSONField()

    objects = OrganisationManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-occurred_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("organisation", "event_id"),
                name="unique_progress_event_id_per_organisation",
            )
        ]
        indexes = [
            models.Index(fields=("organisation", "work_order", "occurred_at")),
            models.Index(fields=("organisation", "actor", "occurred_at")),
        ]

    def clean(self):
        errors = {}
        if self.work_order_id and self.work_order.organisation_id != self.organisation_id:
            errors["work_order"] = "Work order must belong to the event organisation."
        if self.actor_id and self.actor.organisation_id != self.organisation_id:
            errors["actor"] = "Actor must belong to the event organisation."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.event_id} ({self.event_type})"
