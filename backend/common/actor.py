from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import AuthenticationFailed

from common.exceptions import OrganisationContextError


@dataclass(frozen=True, slots=True)
class ActorContext:
    user: Any
    organisation_user: Any
    organisation: Any
    role: str


def resolve_actor(request) -> ActorContext:
    user = request.user
    if not user or not user.is_authenticated:
        raise AuthenticationFailed("Authentication credentials were not provided.")

    try:
        organisation_user = user.organisation_user
    except (AttributeError, ObjectDoesNotExist):
        raise OrganisationContextError() from None

    if not organisation_user.is_active or not organisation_user.organisation.is_active:
        raise OrganisationContextError()

    actor = ActorContext(
        user=user,
        organisation_user=organisation_user,
        organisation=organisation_user.organisation,
        role=organisation_user.role,
    )
    request.actor = actor
    return actor
