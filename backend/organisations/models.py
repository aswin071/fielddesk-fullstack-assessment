from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.models import BaseModel, OrganisationBaseModel


def default_storage_limit_bytes():
    return settings.ORGANISATION_STORAGE_LIMIT_BYTES


class Organisation(BaseModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    storage_limit_bytes = models.PositiveBigIntegerField(
        default=default_storage_limit_bytes,
        validators=[MinValueValidator(1)],
    )
    storage_used_bytes = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(storage_used_bytes__lte=models.F("storage_limit_bytes")),
                name="organisation_storage_usage_within_limit",
            )
        ]

    def __str__(self):
        return self.name


class OrganisationUserRole(models.TextChoices):
    OWNER = "owner", "Owner"
    DISPATCHER = "dispatcher", "Dispatcher"
    TECHNICIAN = "technician", "Technician"


class OrganisationUser(OrganisationBaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organisation_user",
    )
    role = models.CharField(max_length=20, choices=OrganisationUserRole.choices, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("user__email",)
        constraints = [
            models.UniqueConstraint(
                fields=("organisation", "user"),
                name="unique_user_per_organisation",
            )
        ]
        indexes = [models.Index(fields=("organisation", "role", "is_active"))]

    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()})"
