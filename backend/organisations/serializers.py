from rest_framework import serializers

from organisations.models import Organisation


class OrganisationSerializer(serializers.ModelSerializer):
    storageLimitBytes = serializers.IntegerField(source="storage_limit_bytes", read_only=True)
    storageUsedBytes = serializers.IntegerField(source="storage_used_bytes", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Organisation
        fields = (
            "id",
            "name",
            "slug",
            "storageLimitBytes",
            "storageUsedBytes",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "slug",
            "storageLimitBytes",
            "storageUsedBytes",
            "createdAt",
            "updatedAt",
        )
