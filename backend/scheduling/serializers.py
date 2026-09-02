from django.utils import timezone
from rest_framework import serializers


class WorkOrderAssignmentSerializer(serializers.Serializer):
    technicianId = serializers.UUIDField(source="technician_id")
    scheduledStart = serializers.DateTimeField(source="scheduled_start")
    scheduledEnd = serializers.DateTimeField(source="scheduled_end")

    def validate(self, attrs):
        if attrs["scheduled_start"] < timezone.now():
            raise serializers.ValidationError(
                {"scheduledStart": ["Cannot schedule a work order in the past."]}
            )
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError(
                {"scheduledEnd": ["Must be later than scheduledStart."]}
            )
        return attrs
