from rest_framework import serializers

from workorders.models import WorkOrderStatus

ALLOWED_STATUS_TRANSITIONS = {
    WorkOrderStatus.DRAFT: {WorkOrderStatus.SCHEDULED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.SCHEDULED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.IN_PROGRESS: {
        WorkOrderStatus.BLOCKED,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.CANCELLED,
    },
    WorkOrderStatus.BLOCKED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.COMPLETED: set(),
    WorkOrderStatus.CANCELLED: set(),
}


def validate_status_transition(work_order, next_status):
    if next_status == work_order.status:
        return
    if next_status not in ALLOWED_STATUS_TRANSITIONS[work_order.status]:
        raise serializers.ValidationError(
            {
                "status": [
                    f"Cannot change status from {work_order.status} to {next_status}."
                ]
            }
        )
    if next_status == WorkOrderStatus.SCHEDULED and (
        not work_order.assigned_technician_id
        or not work_order.scheduled_start
        or not work_order.scheduled_end
    ):
        raise serializers.ValidationError(
            {"status": ["A work order must be assigned and scheduled before activation."]}
        )
    if next_status in {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.BLOCKED} and not (
        work_order.assigned_technician_id
    ):
        raise serializers.ValidationError(
            {"status": ["An assigned technician is required for this status."]}
        )

