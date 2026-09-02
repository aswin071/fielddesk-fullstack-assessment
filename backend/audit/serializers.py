from rest_framework import serializers

from audit.models import AuditEntry


class AuditActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(source="user.get_full_name")
    role = serializers.CharField()


class AuditEntrySerializer(serializers.ModelSerializer):
    targetType = serializers.CharField(source="target_type")
    targetId = serializers.UUIDField(source="target_id")
    correlationId = serializers.CharField(source="correlation_id")
    createdAt = serializers.DateTimeField(source="created_at")
    actor = AuditActorSerializer(allow_null=True)

    class Meta:
        model = AuditEntry
        fields = (
            "id",
            "action",
            "targetType",
            "targetId",
            "actor",
            "before",
            "after",
            "metadata",
            "correlationId",
            "createdAt",
        )
