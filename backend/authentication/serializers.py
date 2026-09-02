from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from organisations.models import OrganisationUser
from users.managers import UserManager
from users.models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    default_error_messages = {"invalid_credentials": "Invalid email or password."}

    def validate(self, attrs):
        email = UserManager.normalize_email_address(attrs["email"])
        user = authenticate(
            request=self.context.get("request"), email=email, password=attrs["password"]
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])
        try:
            organisation_user = OrganisationUser.objects.select_related("organisation").get(
                user=user,
                is_active=True,
                organisation__is_active=True,
            )
        except OrganisationUser.DoesNotExist:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"]) from None
        attrs["user"] = user
        attrs["organisation_user"] = organisation_user
        return attrs


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        raw_refresh = self.context["request"].COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            raise AuthenticationFailed("A valid refresh session is required.")

        try:
            token = RefreshToken(raw_refresh)
        except TokenError:
            raise AuthenticationFailed("A valid refresh session is required.") from None
        user_id = token.get("user_id")
        try:
            User.objects.get(
                id=user_id,
                is_active=True,
                organisation_user__is_active=True,
                organisation_user__organisation__is_active=True,
            )
        except (User.DoesNotExist, ValueError):
            raise AuthenticationFailed("A valid refresh session is required.") from None

        return super().validate({"refresh": raw_refresh})


def user_session_data(organisation_user):
    user = organisation_user.user
    organisation = organisation_user.organisation
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "fullName": user.get_full_name(),
        },
        "role": organisation_user.role,
        "organisation": {
            "id": str(organisation.id),
            "name": organisation.name,
            "slug": organisation.slug,
        },
    }
