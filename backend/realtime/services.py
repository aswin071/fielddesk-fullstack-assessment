import json
import logging
from datetime import UTC, datetime

from django.conf import settings
from django.db import transaction
from redis import Redis

logger = logging.getLogger("fielddesk.realtime")
ALLOWED_EVENT_TYPES = {
    "attachment.added",
    "attachment.deleted",
    "notification.updated",
    "work_order.created",
    "work_order.progressed",
    "work_order.scheduled",
    "work_order.updated",
}
PUBLISH_SCRIPT = """
local sequence = redis.call('INCR', KEYS[1])
local event = cjson.decode(ARGV[1])
event['cursor'] = tostring(sequence)
local encoded = cjson.encode(event)
redis.call('PUBLISH', KEYS[2], encoded)
return encoded
"""


def organisation_channel(organisation_id):
    return f"fielddesk:realtime:organisation:{organisation_id}"


def organisation_sequence_key(organisation_id):
    return f"fielddesk:realtime:sequence:{organisation_id}"


def publish_realtime_event(*, organisation_id, event_type, target_id, changes=None):
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("Unsupported realtime event type")
    event = {
        "type": event_type,
        "targetId": str(target_id),
        "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "changes": dict(changes or {}),
    }
    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        client.eval(
            PUBLISH_SCRIPT,
            2,
            organisation_sequence_key(organisation_id),
            organisation_channel(organisation_id),
            json.dumps(event, separators=(",", ":")),
        )
    except Exception:
        logger.exception(
            "realtime_publish_failed",
            extra={
                "event": "realtime_publish_failed",
                "event_type": event_type,
                "target_id": str(target_id),
            },
        )


def publish_realtime_after_commit(*, organisation_id, event_type, target_id, changes=None):
    transaction.on_commit(
        lambda: publish_realtime_event(
            organisation_id=organisation_id,
            event_type=event_type,
            target_id=target_id,
            changes=changes,
        )
    )
