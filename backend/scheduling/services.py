from django.db import transaction
from django.http import Http404

from audit.services import record_audit
from common.exceptions import ScheduleConflictError
from notifications.services import create_assignment_delivery
from organisations.models import OrganisationUser, OrganisationUserRole
from realtime.services import publish_realtime_after_commit
from workorders.models import WorkOrder, WorkOrderStatus
from workorders.services import work_order_snapshot

ASSIGNABLE_STATUSES = {WorkOrderStatus.DRAFT, WorkOrderStatus.SCHEDULED}


@transaction.atomic
def assign_work_order(
    *,
    actor,
    work_order_id,
    technician_id,
    scheduled_start,
    scheduled_end,
):
    try:
        work_order = (
            WorkOrder.objects.select_for_update()
            .for_organisation(actor.organisation)
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise Http404 from None

    if work_order.status not in ASSIGNABLE_STATUSES:
        raise ScheduleConflictError(
            f"A {work_order.status} work order cannot be assigned or rescheduled."
        )

    before = work_order_snapshot(work_order)

    technician_ids = {technician_id}
    if work_order.assigned_technician_id:
        technician_ids.add(work_order.assigned_technician_id)

    locked_technicians = list(
        OrganisationUser.objects.select_for_update()
        .for_organisation(actor.organisation)
        .filter(id__in=technician_ids)
        .select_related("user")
        .order_by("id")
    )
    technician_by_id = {technician.id: technician for technician in locked_technicians}
    technician = technician_by_id.get(technician_id)
    if (
        technician is None
        or technician.role != OrganisationUserRole.TECHNICIAN
        or not technician.is_active
        or not technician.user.is_active
    ):
        raise Http404

    conflict = (
        WorkOrder.objects.for_organisation(actor.organisation)
        .filter(
            assigned_technician=technician,
            scheduled_start__lt=scheduled_end,
            scheduled_end__gt=scheduled_start,
        )
        .exclude(pk=work_order.pk)
        .exclude(status=WorkOrderStatus.CANCELLED)
        .only("id", "reference_number")
        .first()
    )
    if conflict:
        raise ScheduleConflictError()

    work_order.assigned_technician = technician
    work_order.scheduled_start = scheduled_start
    work_order.scheduled_end = scheduled_end
    if work_order.status == WorkOrderStatus.DRAFT:
        work_order.status = WorkOrderStatus.SCHEDULED
    work_order.assignment_revision += 1
    work_order.full_clean()
    work_order.save(
        update_fields=(
            "assigned_technician",
            "scheduled_start",
            "scheduled_end",
            "status",
            "assignment_revision",
            "updated_at",
        )
    )
    record_audit(
        organisation=actor.organisation,
        actor=actor.organisation_user,
        action="work_order.assigned",
        target_type="WorkOrder",
        target_id=work_order.id,
        related_work_order=work_order,
        before=before,
        after=work_order_snapshot(work_order),
        metadata={"assignmentRevision": work_order.assignment_revision},
    )
    create_assignment_delivery(work_order=work_order)
    publish_realtime_after_commit(
        organisation_id=work_order.organisation_id,
        event_type="work_order.scheduled",
        target_id=work_order.id,
        changes={
            "status": work_order.status,
            "technicianId": str(technician.id),
            "assignmentRevision": work_order.assignment_revision,
        },
    )
    return work_order
