from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from attachments.models import Attachment
from attachments.serializers import AttachmentSerializer
from attachments.services import create_attachment, delete_attachment, validate_upload
from common.actor import resolve_actor
from common.responses import success_response
from organisations.models import OrganisationUserRole
from workorders.models import WorkOrder
from workorders.selectors import visible_work_orders


def _visible_work_order(actor, work_order_id):
    try:
        return visible_work_orders(actor).get(pk=work_order_id)
    except WorkOrder.DoesNotExist:
        raise Http404 from None


class AttachmentCollectionView(APIView):
    parser_classes = [MultiPartParser]

    def get(self, request, work_order_id):
        actor = resolve_actor(request)
        work_order = _visible_work_order(actor, work_order_id)
        attachments = Attachment.objects.for_organisation(actor.organisation).filter(
            work_order=work_order
        )
        return success_response(AttachmentSerializer(attachments, many=True).data)

    def post(self, request, work_order_id):
        actor = resolve_actor(request)
        work_order = _visible_work_order(actor, work_order_id)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["This field is required."]})
        validated = validate_upload(upload)
        attachment = create_attachment(
            actor=actor,
            work_order=work_order,
            validated=validated,
        )
        return success_response(
            AttachmentSerializer(attachment).data,
            status_code=status.HTTP_201_CREATED,
        )


class AttachmentDetailView(APIView):
    def _attachment(self, actor, work_order_id, attachment_id):
        work_order = _visible_work_order(actor, work_order_id)
        try:
            attachment = Attachment.objects.for_organisation(actor.organisation).get(
                pk=attachment_id,
                work_order=work_order,
            )
        except Attachment.DoesNotExist:
            raise Http404 from None
        return work_order, attachment

    def get(self, request, work_order_id, attachment_id):
        actor = resolve_actor(request)
        _, attachment = self._attachment(actor, work_order_id, attachment_id)
        try:
            stored_file = default_storage.open(attachment.storage_key, "rb")
        except FileNotFoundError:
            raise Http404 from None
        response = FileResponse(
            stored_file,
            content_type=attachment.content_type,
            as_attachment=True,
            filename=attachment.display_name,
        )
        response["Content-Length"] = attachment.size_bytes
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def delete(self, request, work_order_id, attachment_id):
        actor = resolve_actor(request)
        if actor.role not in {
            OrganisationUserRole.OWNER,
            OrganisationUserRole.DISPATCHER,
        }:
            self.permission_denied(request)
        work_order, _ = self._attachment(actor, work_order_id, attachment_id)
        delete_attachment(
            actor=actor,
            attachment_id=attachment_id,
            work_order=work_order,
        )
        return success_response(status_code=status.HTTP_204_NO_CONTENT)
