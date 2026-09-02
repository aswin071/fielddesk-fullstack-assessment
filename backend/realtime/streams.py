import json
import time

from django.conf import settings
from redis.asyncio import Redis

from realtime.services import (
    ALLOWED_EVENT_TYPES,
    organisation_channel,
    organisation_sequence_key,
)


def _sse_event(event_type, data, event_id=None):
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


async def organisation_event_stream(
    organisation_id,
    *,
    last_event_id=None,
    heartbeat_seconds=None,
    max_connection_seconds=None,
):
    heartbeat_seconds = heartbeat_seconds or settings.REALTIME_HEARTBEAT_SECONDS
    max_connection_seconds = (
        max_connection_seconds or settings.REALTIME_MAX_CONNECTION_SECONDS
    )
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    started = time.monotonic()
    try:
        await pubsub.subscribe(organisation_channel(organisation_id))
        current_cursor = await client.get(organisation_sequence_key(organisation_id)) or "0"
        if last_event_id is not None:
            yield _sse_event(
                "sync_required",
                {"reason": "reconnect", "cursor": current_cursor},
                current_cursor,
            )
        else:
            yield _sse_event("connected", {"cursor": current_cursor}, current_cursor)

        while time.monotonic() - started < max_connection_seconds:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=heartbeat_seconds,
            )
            if message is None:
                yield ": heartbeat\n\n"
                continue
            try:
                event = json.loads(message["data"])
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            cursor = event.get("cursor")
            event_type = event.get("type")
            target_id = event.get("targetId")
            if (
                not str(cursor).isdigit()
                or event_type not in ALLOWED_EVENT_TYPES
                or not isinstance(target_id, str)
                or len(target_id) > 64
            ):
                continue
            safe_event = {
                "cursor": str(cursor),
                "type": event_type,
                "targetId": target_id,
                "occurredAt": event.get("occurredAt"),
                "changes": event.get("changes") if isinstance(event.get("changes"), dict) else {},
            }
            yield _sse_event(event_type, safe_event, cursor)

        yield _sse_event("reconnect", {"reason": "connection_refresh"})
    finally:
        await pubsub.unsubscribe(organisation_channel(organisation_id))
        await pubsub.aclose()
        await client.aclose()
