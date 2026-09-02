from rest_framework import serializers

from attachments.models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source="display_name")
    contentType = serializers.CharField(source="content_type")
    sizeBytes = serializers.IntegerField(source="size_bytes")
    checksumSha256 = serializers.CharField(source="checksum_sha256")
    uploadedBy = serializers.UUIDField(source="uploader_id")
    createdAt = serializers.DateTimeField(source="created_at")
    downloadUrl = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "id",
            "fileName",
            "contentType",
            "sizeBytes",
            "checksumSha256",
            "uploadedBy",
            "createdAt",
            "downloadUrl",
        )

    def get_downloadUrl(self, attachment):
        return (
            f"/api/v1/work-orders/{attachment.work_order_id}/attachments/{attachment.id}"
        )
