from rest_framework import status
from rest_framework.views import APIView

from common.actor import resolve_actor
from common.permissions import IsOwner, IsOwnerOrDispatcher
from common.responses import success_response
from common.tenancy import organisation_object_or_404
from organisations.models import OrganisationUser, OrganisationUserRole
from users.serializers import (
    OrganisationUserCreateSerializer,
    OrganisationUserSerializer,
    OrganisationUserUpdateSerializer,
)


class OrganisationUserListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwner()]
        return [IsOwnerOrDispatcher()]

    def get(self, request):
        actor = resolve_actor(request)
        queryset = OrganisationUser.objects.for_organisation(actor.organisation).select_related(
            "user"
        )
        if actor.role != OrganisationUserRole.OWNER:
            queryset = queryset.filter(role=OrganisationUserRole.TECHNICIAN, is_active=True)
        return success_response(OrganisationUserSerializer(queryset, many=True).data)

    def post(self, request):
        actor = resolve_actor(request)
        serializer = OrganisationUserCreateSerializer(data=request.data, context={"actor": actor})
        serializer.is_valid(raise_exception=True)
        organisation_user = serializer.save()
        return success_response(
            OrganisationUserSerializer(organisation_user).data,
            status_code=status.HTTP_201_CREATED,
        )


class OrganisationUserDetailView(APIView):
    permission_classes = [IsOwner]

    def patch(self, request, user_id):
        actor = resolve_actor(request)
        organisation_user = organisation_object_or_404(
            OrganisationUser.objects.select_related("user"),
            actor,
            id=user_id,
        )
        serializer = OrganisationUserUpdateSerializer(
            organisation_user,
            data=request.data,
            partial=True,
            context={"actor": actor},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(OrganisationUserSerializer(organisation_user).data)
