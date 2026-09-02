from django.contrib import admin

from workorders.models import WorkOrder


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "title",
        "organisation",
        "status",
        "priority",
        "assigned_technician",
        "scheduled_start",
    )
    list_filter = ("organisation", "status", "priority")
    search_fields = ("reference_number", "title", "description", "site_name")
    readonly_fields = ("reference_number", "created_at", "updated_at", "deleted_at")

