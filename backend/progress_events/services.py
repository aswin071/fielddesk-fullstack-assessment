import hashlib
import json
from datetime import UTC

from django.db import connection, transaction
from django.http import Http404

from audit.services import record_audit
from common.exceptions import IdempotencyKeyReusedError
from progress_events.models import ProgressEvent, ProgressEventType
from realtime.services import publish_realtime_after_commit
from workorders.models import WorkOrder
from workorders.transitions import validate_status_transition


def _canonical_timestamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def progress_event_hash(*, event_id, work_order_id, event_type, occurred_at, payload):
    canonical = json.dumps(
        {
            "eventId": event_id,
            "workOrderId": str(work_order_id),
            "type": event_type,
            "occurredAt": _canonical_timestamp(occurred_at),
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _advisory_lock_key(organisation_id, event_id):
    digest = hashlib.blake2b(
        f"{organisation_id}:{event_id}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


@transaction.atomic
def process_progress_event(
    *,
    actor,
    event_id,
    work_order_id,
    event_type,
    occurred_at,
    payload,
    original_event,
):
    request_hash = progress_event_hash(
        event_id=event_id,
        work_order_id=work_order_id,
        event_type=event_type,
        occurred_at=occurred_at,
        payload=payload,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            [_advisory_lock_key(actor.organisation.pk, event_id)],
        )

    existing = (
        ProgressEvent.objects.for_organisation(actor.organisation)
        .select_related("work_order", "actor")
        .filter(event_id=event_id)
        .first()
    )
    if existing:
        if existing.actor_id != actor.organisation_user.id:
            raise Http404
        if existing.request_hash != request_hash:
            raise IdempotencyKeyReusedError()
        return existing, False

    try:
        work_order = (
            WorkOrder.objects.select_for_update()
            .for_organisation(actor.organisation)
            .get(pk=work_order_id, assigned_technician=actor.organisation_user)
        )
    except WorkOrder.DoesNotExist:
        raise Http404 from None

    resulting_status = work_order.status
    previous_status = work_order.status
    if event_type == ProgressEventType.STATUS_CHANGED:
        resulting_status = payload["status"]
        validate_status_transition(work_order, resulting_status)
        work_order.status = resulting_status
        work_order.save(update_fields=("status", "updated_at"))

    result = {
        "eventId": event_id,
        "workOrderId": str(work_order.id),
        "status": resulting_status,
        "accepted": True,
    }
    progress_event = ProgressEvent(
        organisation=actor.organisation,
        actor=actor.organisation_user,
        work_order=work_order,
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        payload=payload,
        original_event=original_event,
        request_hash=request_hash,
        result=result,
    )
    progress_event.full_clean()
    progress_event.save()
    record_audit(
        organisation=actor.organisation,
        actor=actor.organisation_user,
        action="progress_event.accepted",
        target_type="ProgressEvent",
        target_id=progress_event.id,
        related_work_order=work_order,
        before={"status": previous_status},
        after={"status": resulting_status},
        metadata={"eventId": event_id, "eventType": event_type},
    )
    publish_realtime_after_commit(
        organisation_id=work_order.organisation_id,
        event_type="work_order.progressed",
        target_id=work_order.id,
        changes={"eventType": event_type, "status": resulting_status},
    )
    return progress_event, True
