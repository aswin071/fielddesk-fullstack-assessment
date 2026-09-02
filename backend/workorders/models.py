from django.core.exceptions import ValidationError
from django.db import models

from common.models import OrganisationBaseModel
from organisations.models import OrganisationUser, OrganisationUserRole


class WorkOrderPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class WorkOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    IN_PROGRESS = "in_progress", "In progress"
    BLOCKED = "blocked", "Blocked"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class WorkOrder(OrganisationBaseModel):
    reference_number = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=10,
        choices=WorkOrderPriority.choices,
        default=WorkOrderPriority.MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.DRAFT,
        db_index=True,
    )
    assigned_technician = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="assigned_work_orders",
        null=True,
        blank=True,
    )
    scheduled_start = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_end = models.DateTimeField(null=True, blank=True, db_index=True)
    assignment_revision = models.PositiveIntegerField(default=0, editable=False)
    site_name = models.CharField(max_length=200)
    creator = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="created_work_orders",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organisation", "reference_number"),
                name="unique_work_order_reference_per_organisation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scheduled_start__isnull=True, scheduled_end__isnull=True)
                    | models.Q(scheduled_start__isnull=False, scheduled_end__isnull=False)
                ),
                name="work_order_schedule_window_is_paired",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scheduled_start__isnull=True)
                    | models.Q(scheduled_end__gt=models.F("scheduled_start"))
                ),
                name="work_order_schedule_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=("organisation", "status", "created_at")),
            models.Index(fields=("organisation", "priority", "created_at")),
            models.Index(fields=("organisation", "assigned_technician", "scheduled_start")),
        ]

    def clean(self):
        errors = {}
        if self.creator_id and self.creator.organisation_id != self.organisation_id:
            errors["creator"] = "Creator must belong to the work order organisation."
        if self.assigned_technician_id:
            if self.assigned_technician.organisation_id != self.organisation_id:
                errors["assigned_technician"] = "Technician must belong to the organisation."
            elif self.assigned_technician.role != OrganisationUserRole.TECHNICIAN:
                errors["assigned_technician"] = "Assigned user must be a Technician."
        if bool(self.scheduled_start) != bool(self.scheduled_end):
            errors["scheduled_start"] = "Scheduled start and end must be supplied together."
        if self.scheduled_start and self.scheduled_end <= self.scheduled_start:
            errors["scheduled_end"] = "Scheduled end must be later than scheduled start."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.reference_number}: {self.title}"
