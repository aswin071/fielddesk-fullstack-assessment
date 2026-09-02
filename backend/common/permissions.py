from rest_framework.permissions import BasePermission

from common.actor import resolve_actor

OWNER = "owner"
DISPATCHER = "dispatcher"
TECHNICIAN = "technician"


class HasFieldDeskRole(BasePermission):
    allowed_roles: frozenset[str] = frozenset()
    message = "Your role does not permit this action."

    def has_permission(self, request, view):
        actor = resolve_actor(request)
        return actor.role in self.allowed_roles


class IsOwner(HasFieldDeskRole):
    allowed_roles = frozenset({OWNER})


class IsDispatcher(HasFieldDeskRole):
    allowed_roles = frozenset({DISPATCHER})


class IsTechnician(HasFieldDeskRole):
    allowed_roles = frozenset({TECHNICIAN})


class IsOwnerOrDispatcher(HasFieldDeskRole):
    allowed_roles = frozenset({OWNER, DISPATCHER})

