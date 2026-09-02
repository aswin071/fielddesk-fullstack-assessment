import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from progress_events.models import ProgressEventType
from workorders.models import WorkOrderStatus

EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
STATUS_EVENT_KEYS = {"status", "note"}
NOTE_EVENT_KEYS = {"note"}
TECHNICIAN_STATUSES = {
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.BLOCKED,
    WorkOrderStatus.COMPLETED,
}


class ProgressEventSerializer(serializers.Serializer):
    eventId = serializers.CharField(source="event_id", max_length=100)
    workOrderId = serializers.UUIDField(source="work_order_id")
    type = serializers.ChoiceField(source="event_type", choices=ProgressEventType.choices)
    occurredAt = serializers.DateTimeField(source="occurred_at")
    payload = serializers.JSONField()

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: ["Unknown field."] for field in sorted(unknown)}
            )
        return super().to_internal_value(data)

    def validate_eventId(self, value):
        if not EVENT_ID_PATTERN.fullmatch(value):
            raise serializers.ValidationError("Contains unsupported characters.")
        return value

    def validate_occurredAt(self, value):
        now = timezone.now()
        future_seconds = settings.PROGRESS_EVENT_MAX_FUTURE_SECONDS
        maximum_age = timedelta(days=settings.PROGRESS_EVENT_MAX_AGE_DAYS)
        if value > now + timedelta(seconds=future_seconds):
            raise serializers.ValidationError("Cannot be more than five minutes in the future.")
        if value < now - maximum_age:
            raise serializers.ValidationError("Is outside the accepted event-history window.")
        return value

    def validate(self, attrs):
        payload = attrs["payload"]
        if not isinstance(payload, dict):
            raise serializers.ValidationError({"payload": ["Must be a JSON object."]})

        event_type = attrs["event_type"]
        allowed_keys = (
            STATUS_EVENT_KEYS
            if event_type == ProgressEventType.STATUS_CHANGED
            else NOTE_EVENT_KEYS
        )
        unknown = set(payload) - allowed_keys
        if unknown:
            raise serializers.ValidationError(
                {"payload": [f"Unknown payload field: {field}." for field in sorted(unknown)]}
            )

        note = payload.get("note")
        if note is not None and (not isinstance(note, str) or not note.strip()):
            raise serializers.ValidationError({"payload": ["note must be a non-empty string."]})
        if isinstance(note, str) and len(note) > 1000:
            raise serializers.ValidationError({"payload": ["note cannot exceed 1000 characters."]})

        if event_type == ProgressEventType.STATUS_CHANGED:
            status_value = payload.get("status")
            if status_value not in TECHNICIAN_STATUSES:
                raise serializers.ValidationError(
                    {"payload": ["status must be in_progress, blocked, or completed."]}
                )
        elif note is None:
            raise serializers.ValidationError({"payload": ["note is required."]})
        return attrs

