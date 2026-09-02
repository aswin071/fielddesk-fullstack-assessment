from rest_framework import status
from rest_framework.views import APIView

from common.actor import resolve_actor
from common.permissions import IsTechnician
from common.responses import success_response
from progress_events.serializers import ProgressEventSerializer
from progress_events.services import process_progress_event
from progress_events.throttles import ProgressEventThrottle


class ProgressEventCreateView(APIView):
    permission_classes = [IsTechnician]
    throttle_classes = [ProgressEventThrottle]

    def post(self, request):
        actor = resolve_actor(request)
        serializer = ProgressEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        original_event = {
            field: request.data[field]
            for field in ("eventId", "workOrderId", "type", "occurredAt", "payload")
        }
        progress_event, created = process_progress_event(
            actor=actor,
            original_event=original_event,
            **serializer.validated_data,
        )
        return success_response(
            progress_event.result,
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            meta={"idempotentReplay": not created},
        )

