from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.cookies import clear_refresh_cookie, set_refresh_cookie
from authentication.serializers import (
    CookieTokenRefreshSerializer,
    LoginSerializer,
    user_session_data,
)
from authentication.throttles import LoginIdentityThrottle, LoginIpThrottle
from common.actor import resolve_actor
from common.responses import success_response


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginIpThrottle, LoginIdentityThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        organisation_user = serializer.validated_data["organisation_user"]
        refresh = RefreshToken.for_user(user)
        response = success_response(
            {
                "accessToken": str(refresh.access_token),
                **user_session_data(organisation_user),
            }
        )
        set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CookieTokenRefreshSerializer(data={}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        response = success_response({"accessToken": serializer.validated_data["access"]})
        set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass
        response = success_response(None, status_code=status.HTTP_200_OK)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = resolve_actor(request)
        return success_response(user_session_data(actor.organisation_user))
