import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Provides non-sequential public identifiers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return self.active().update(deleted_at=timezone.now())

    def restore(self):
        return self.deleted().update(deleted_at=None)

    def hard_delete(self):
        return super().delete()


class ActiveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    pass


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, editable=False)

    objects = ActiveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(using=using, update_fields=("deleted_at",))

    def restore(self, using=None):
        if self.deleted_at is not None:
            self.deleted_at = None
            self.save(using=using, update_fields=("deleted_at",))

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)


class OrganisationScopedQuerySet(SoftDeleteQuerySet):
    def for_organisation(self, organisation):
        if organisation is None:
            raise ValueError("An organisation is required for an organisation-scoped query")
        organisation_id = getattr(organisation, "pk", organisation)
        return self.filter(organisation_id=organisation_id)


class OrganisationQuerySet(models.QuerySet):
    def for_organisation(self, organisation):
        if organisation is None:
            raise ValueError("An organisation is required for an organisation-scoped query")
        organisation_id = getattr(organisation, "pk", organisation)
        return self.filter(organisation_id=organisation_id)


class OrganisationManager(models.Manager.from_queryset(OrganisationQuerySet)):
    pass


class OrganisationScopedManager(models.Manager.from_queryset(OrganisationScopedQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class OrganisationOwnedModel(models.Model):
    """Base for tenant-owned records; views must still use scoped selectors."""

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_records",
    )

    class Meta:
        abstract = True


class ImmutableModel(models.Model):
    """Rejects ordinary mutation after initial persistence."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f"{type(self).__name__} records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{type(self).__name__} records cannot be deleted")


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Default base for mutable, soft-deletable FieldDesk entities."""

    class Meta:
        abstract = True


class OrganisationBaseModel(BaseModel, OrganisationOwnedModel):
    """Default base for mutable organisation-owned entities."""

    objects = OrganisationScopedManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
