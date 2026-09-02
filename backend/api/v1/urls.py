from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.responses import success_response


class ApiIndexView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return success_response({"name": "FieldDesk API", "version": "v1"})


urlpatterns = [
    path("", ApiIndexView.as_view(), name="api-index"),
    path("auth/", include("authentication.urls")),
    path("organisation/", include("organisations.urls")),
    path("users/", include("users.urls")),
    path("", include("workorders.urls")),
    path("", include("scheduling.urls")),
    path("", include("progress_events.urls")),
    path("", include("attachments.urls")),
    path("", include("realtime.urls")),
    path("", include("audit.urls")),
    path("", include("reporting.urls")),
]
