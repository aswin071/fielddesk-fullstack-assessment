from django.db.models import Q

from organisations.models import OrganisationUserRole
from workorders.models import WorkOrder

ORDERING_FIELDS = {
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "scheduledStart": "scheduled_start",
    "priority": "priority",
    "status": "status",
    "referenceNumber": "reference_number",
}


def visible_work_orders(actor):
    queryset = WorkOrder.objects.for_organisation(actor.organisation)
    if actor.role == OrganisationUserRole.TECHNICIAN:
        queryset = queryset.filter(assigned_technician=actor.organisation_user)
    return queryset.select_related(
        "creator__user",
        "assigned_technician__user",
    )


def filtered_work_orders(actor, params):
    queryset = visible_work_orders(actor)
    search = params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(reference_number__icontains=search)
            | Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(site_name__icontains=search)
        )
    if status := params.get("status"):
        queryset = queryset.filter(status=status)
    if priority := params.get("priority"):
        queryset = queryset.filter(priority=priority)
    if technician_id := params.get("technicianId"):
        queryset = queryset.filter(assigned_technician_id=technician_id)
    if scheduled_from := params.get("scheduledFrom"):
        queryset = queryset.filter(scheduled_end__gte=scheduled_from)
    if scheduled_to := params.get("scheduledTo"):
        queryset = queryset.filter(scheduled_start__lte=scheduled_to)

    requested_ordering = params.get("ordering", "-createdAt")
    descending = requested_ordering.startswith("-")
    public_field = requested_ordering.removeprefix("-")
    model_field = ORDERING_FIELDS.get(public_field, "created_at")
    prefix = "-" if descending else ""
    return queryset.order_by(f"{prefix}{model_field}", "-id")

