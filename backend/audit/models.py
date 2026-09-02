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


class AuditEntry(
    UUIDModel,
    TimeStampedModel,
    OrganisationOwnedModel,
    ImmutableModel,
):
    actor = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="audit_entries",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=50)
    target_id = models.UUIDField()
    related_work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="audit_entries",
        null=True,
        blank=True,
    )
    correlation_id = models.CharField(max_length=128, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = OrganisationManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("organisation", "related_work_order", "created_at")),
            models.Index(fields=("organisation", "target_type", "target_id")),
            models.Index(fields=("organisation", "action", "created_at")),
        ]

    def clean(self):
        errors = {}
        if self.actor_id and self.actor.organisation_id != self.organisation_id:
            errors["actor"] = "Actor must belong to the audit organisation."
        if (
            self.related_work_order_id
            and self.related_work_order.organisation_id != self.organisation_id
        ):
            errors["related_work_order"] = (
                "Related work order must belong to the audit organisation."
            )
        if errors:
            raise ValidationError(errors)
