import hashlib
import re
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import PurePath

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import Http404
from rest_framework import serializers

from attachments.models import Attachment
from audit.services import record_audit
from common.exceptions import StorageQuotaExceededError
from organisations.models import Organisation
from realtime.services import publish_realtime_after_commit

ALLOWED_FILES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "application/pdf": {".pdf"},
}


@dataclass
class ValidatedUpload:
    temporary_file: object
    display_name: str
    extension: str
    content_type: str
    size_bytes: int
    checksum_sha256: str

    def close(self):
        self.temporary_file.close()


def _detected_content_type(header):
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _safe_display_name(original_name):
    leaf_name = re.split(r"[\\/]", original_name or "")[-1]
    normalized = unicodedata.normalize("NFKC", leaf_name)
    cleaned = "".join(character for character in normalized if character.isprintable())
    cleaned = cleaned.strip().strip(".")
    if not cleaned:
        raise serializers.ValidationError({"file": ["A valid filename is required."]})
    return cleaned[:255]


def validate_upload(upload):
    display_name = _safe_display_name(upload.name)
    extension = PurePath(display_name).suffix.lower()
    maximum = settings.ATTACHMENT_MAX_BYTES
    digest = hashlib.sha256()
    total = 0
    header = b""
    temporary_file = tempfile.SpooledTemporaryFile(max_size=min(maximum, 2 * 1024 * 1024))
    try:
        for chunk in upload.chunks():
            total += len(chunk)
            if total > maximum:
                raise serializers.ValidationError(
                    {"file": [f"File cannot exceed {maximum} bytes."]}
                )
            if len(header) < 16:
                header += chunk[: 16 - len(header)]
            digest.update(chunk)
            temporary_file.write(chunk)
        if total == 0:
            raise serializers.ValidationError({"file": ["File cannot be empty."]})

        content_type = _detected_content_type(header)
        if content_type is None or extension not in ALLOWED_FILES.get(content_type, set()):
            raise serializers.ValidationError(
                {"file": ["Only genuine JPEG, PNG and PDF files are accepted."]}
            )
        declared_type = (upload.content_type or "").lower()
        if declared_type and declared_type not in {content_type, "application/octet-stream"}:
            raise serializers.ValidationError(
                {"file": ["Declared and detected file types do not match."]}
            )
        temporary_file.seek(0)
        return ValidatedUpload(
            temporary_file=temporary_file,
            display_name=display_name,
            extension=extension,
            content_type=content_type,
            size_bytes=total,
            checksum_sha256=digest.hexdigest(),
        )
    except Exception:
        temporary_file.close()
        raise


def create_attachment(*, actor, work_order, validated):
    opaque_id = uuid.uuid4()
    requested_key = f"attachments/{opaque_id.hex[:2]}/{opaque_id}{validated.extension}"
    saved_key = None
    try:
        with transaction.atomic():
            organisation = Organisation.objects.select_for_update().get(
                pk=actor.organisation.pk
            )
            projected_usage = organisation.storage_used_bytes + validated.size_bytes
            if projected_usage > organisation.storage_limit_bytes:
                raise StorageQuotaExceededError()

            saved_key = default_storage.save(
                requested_key,
                File(validated.temporary_file, name=str(opaque_id)),
            )
            attachment = Attachment(
                organisation=organisation,
                work_order=work_order,
                uploader=actor.organisation_user,
                storage_key=saved_key,
                display_name=validated.display_name,
                content_type=validated.content_type,
                size_bytes=validated.size_bytes,
                checksum_sha256=validated.checksum_sha256,
            )
            attachment.full_clean()
            attachment.save()
            record_audit(
                organisation=organisation,
                actor=actor.organisation_user,
                action="attachment.added",
                target_type="Attachment",
                target_id=attachment.id,
                related_work_order=work_order,
                after={
                    "fileName": attachment.display_name,
                    "contentType": attachment.content_type,
                    "sizeBytes": attachment.size_bytes,
                    "checksumSha256": attachment.checksum_sha256,
                },
            )
            organisation.storage_used_bytes += validated.size_bytes
            organisation.save(update_fields=("storage_used_bytes", "updated_at"))
            publish_realtime_after_commit(
                organisation_id=organisation.id,
                event_type="attachment.added",
                target_id=work_order.id,
                changes={"attachmentId": str(attachment.id)},
            )
            return attachment
    except Exception:
        if saved_key:
            default_storage.delete(saved_key)
        raise
    finally:
        validated.close()


def delete_attachment(*, actor, attachment_id, work_order):
    with transaction.atomic():
        organisation = Organisation.objects.select_for_update().get(pk=actor.organisation.pk)
        try:
            attachment = (
                Attachment.objects.select_for_update()
                .for_organisation(organisation)
                .get(pk=attachment_id, work_order=work_order)
            )
        except Attachment.DoesNotExist:
            raise Http404 from None
        storage_key = attachment.storage_key
        organisation.storage_used_bytes = max(
            0, organisation.storage_used_bytes - attachment.size_bytes
        )
        organisation.save(update_fields=("storage_used_bytes", "updated_at"))
        record_audit(
            organisation=organisation,
            actor=actor.organisation_user,
            action="attachment.deleted",
            target_type="Attachment",
            target_id=attachment.id,
            related_work_order=work_order,
            before={
                "fileName": attachment.display_name,
                "contentType": attachment.content_type,
                "sizeBytes": attachment.size_bytes,
                "checksumSha256": attachment.checksum_sha256,
            },
        )
        attachment.delete()
        transaction.on_commit(lambda: default_storage.delete(storage_key))
        publish_realtime_after_commit(
            organisation_id=organisation.id,
            event_type="attachment.deleted",
            target_id=work_order.id,
            changes={"attachmentId": str(attachment.id)},
        )
