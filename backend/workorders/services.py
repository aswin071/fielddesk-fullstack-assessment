import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from audit.services import record_audit
from realtime.services import publish_realtime_after_commit
from workorders.models import WorkOrder
from workorders.transitions import validate_status_transition


def _new_reference_number():
    return f"WO-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def work_order_snapshot(work_order):
    return {
        "referenceNumber": work_order.reference_number,
        "title": work_order.title,
        "description": work_order.description,
        "priority": work_order.priority,
        "status": work_order.status,
        "siteName": work_order.site_name,
        "assignedTechnicianId": work_order.assigned_technician_id,
        "scheduledStart": work_order.scheduled_start,
        "scheduledEnd": work_order.scheduled_end,
        "assignmentRevision": work_order.assignment_revision,
    }


def create_work_order(*, actor, validated_data):
    for attempt in range(3):
        try:
            with transaction.atomic():
                work_order = WorkOrder(
                    organisation=actor.organisation,
                    creator=actor.organisation_user,
                    reference_number=_new_reference_number(),
                    **validated_data,
                )
                work_order.full_clean()
                work_order.save()
                record_audit(
                    organisation=actor.organisation,
                    actor=actor.organisation_user,
                    action="work_order.created",
                    target_type="WorkOrder",
                    target_id=work_order.id,
                    related_work_order=work_order,
                    after=work_order_snapshot(work_order),
                )
                publish_realtime_after_commit(
                    organisation_id=work_order.organisation_id,
                    event_type="work_order.created",
                    target_id=work_order.id,
                    changes={"status": work_order.status},
                )
                return work_order
        except IntegrityError:
            if attempt == 2:
                raise
    raise RuntimeError("Unable to generate a work-order reference")


@transaction.atomic
def update_work_order(*, actor, work_order, validated_data):
    locked = (
        WorkOrder.objects.select_for_update()
        .for_organisation(actor.organisation)
        .get(pk=work_order.pk)
    )
    before = work_order_snapshot(locked)
    next_status = validated_data.get("status")
    if next_status:
        validate_status_transition(locked, next_status)
    for field, value in validated_data.items():
        setattr(locked, field, value)
    try:
        locked.full_clean()
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        raise serializers.ValidationError(detail) from exc
    locked.save()
    after = work_order_snapshot(locked)
    changed_fields = [key for key in after if before.get(key) != after.get(key)]
    record_audit(
        organisation=actor.organisation,
        actor=actor.organisation_user,
        action="work_order.updated",
        target_type="WorkOrder",
        target_id=locked.id,
        related_work_order=locked,
        before=before,
        after=after,
        metadata={"changedFields": changed_fields},
    )
    publish_realtime_after_commit(
        organisation_id=locked.organisation_id,
        event_type="work_order.updated",
        target_id=locked.id,
        changes={"fields": sorted(validated_data)},
    )
    return locked
