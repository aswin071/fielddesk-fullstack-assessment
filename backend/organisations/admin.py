from django.contrib import admin

from organisations.models import Organisation, OrganisationUser


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "storage_used_bytes", "storage_limit_bytes")
    search_fields = ("name", "slug")
    readonly_fields = ("storage_used_bytes", "created_at", "updated_at", "deleted_at")


@admin.register(OrganisationUser)
class OrganisationUserAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "role", "is_active")
    list_filter = ("organisation", "role", "is_active")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "organisation")

