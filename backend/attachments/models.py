from django.core.exceptions import ValidationError
from django.db import models

from common.models import OrganisationBaseModel
from organisations.models import OrganisationUser
from workorders.models import WorkOrder


class Attachment(OrganisationBaseModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    uploader = models.ForeignKey(
        OrganisationUser,
        on_delete=models.PROTECT,
        related_name="uploaded_attachments",
    )
    storage_key = models.CharField(max_length=200, unique=True)
    display_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50)
    size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("organisation", "work_order", "created_at")),
            models.Index(fields=("organisation", "checksum_sha256")),
        ]

    def clean(self):
        errors = {}
        if self.work_order_id and self.work_order.organisation_id != self.organisation_id:
            errors["work_order"] = "Work order must belong to the attachment organisation."
        if self.uploader_id and self.uploader.organisation_id != self.organisation_id:
            errors["uploader"] = "Uploader must belong to the attachment organisation."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.display_name
