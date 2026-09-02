from rest_framework.views import APIView

from common.actor import resolve_actor
from common.permissions import IsOwner
from common.responses import success_response
from organisations.serializers import OrganisationSerializer


class OrganisationView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsOwner()]
        return super().get_permissions()

    def get(self, request):
        actor = resolve_actor(request)
        return success_response(OrganisationSerializer(actor.organisation).data)

    def patch(self, request):
        actor = resolve_actor(request)
        serializer = OrganisationSerializer(
            actor.organisation,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)

