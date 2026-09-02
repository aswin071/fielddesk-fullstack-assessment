from django.http import StreamingHttpResponse
from rest_framework import serializers
from rest_framework.views import APIView

from common.actor import resolve_actor
from realtime.streams import organisation_event_stream


class RealtimeEventView(APIView):
    def get(self, request):
        actor = resolve_actor(request)
        last_event_id = request.headers.get("Last-Event-ID")
        if last_event_id is not None and (
            not last_event_id.isdigit() or len(last_event_id) > 30
        ):
            raise serializers.ValidationError(
                {"Last-Event-ID": ["Must be a valid numeric event cursor."]}
            )
        response = StreamingHttpResponse(
            organisation_event_stream(
                actor.organisation.id,
                last_event_id=last_event_id,
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response
