import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from rest_framework.exceptions import ValidationError

from common.actor import resolve_actor
from common.context import reset_correlation_id, set_correlation_id
from common.exception_handler import api_exception_handler
from common.exceptions import OrganisationContextError
from common.logging import JsonFormatter
from common.models import BaseModel, ImmutableModel, OrganisationScopedQuerySet
from common.permissions import IsOwnerOrDispatcher


class ExampleBaseModel(BaseModel):
    class Meta:
        app_label = "tests"
        managed = False


class ExampleImmutableModel(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    class Meta:
        app_label = "tests"
        managed = False


def test_base_model_exposes_uuid_timestamps_and_soft_delete():
    fields = {field.name for field in ExampleBaseModel._meta.fields}
    assert {"id", "created_at", "updated_at", "deleted_at"} <= fields
    assert isinstance(ExampleBaseModel._meta.get_field("id"), models.UUIDField)


def test_organisation_scoped_queryset_requires_organisation():
    queryset = OrganisationScopedQuerySet(model=ExampleBaseModel, using="default")
    with pytest.raises(ValueError, match="organisation is required"):
        queryset.for_organisation(None)


def test_immutable_model_rejects_update_and_delete():
    instance = ExampleImmutableModel()
    instance._state.adding = False

    with pytest.raises(DjangoValidationError, match="immutable"):
        instance.save()
    with pytest.raises(DjangoValidationError, match="cannot be deleted"):
        instance.delete()


def test_validation_error_uses_consistent_envelope():
    token = set_correlation_id("request-123")
    try:
        response = api_exception_handler(
            ValidationError({"title": ["This field is required."]}),
            {"view": None, "request": None},
        )
    finally:
        reset_correlation_id(token)

    assert response.status_code == 400
    assert response.data == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The submitted data is invalid.",
            "fields": {"title": ["This field is required."]},
            "correlationId": "request-123",
        }
    }


def test_json_logging_includes_context_and_redacts_sensitive_extras():
    formatter = JsonFormatter()
    record = logging.LogRecord("fielddesk.test", logging.INFO, __file__, 1, "saved", (), None)
    record.event = "test_event"
    record.password = "never-log-this"
    token = set_correlation_id("request-456")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        reset_correlation_id(token)

    assert payload["correlationId"] == "request-456"
    assert payload["event"] == "test_event"
    assert payload["password"] == "[REDACTED]"


def test_correlation_middleware_preserves_valid_header(client):
    response = client.get("/health/live", HTTP_X_CORRELATION_ID="client-request-1")
    assert response["X-Correlation-ID"] == "client-request-1"


def test_correlation_middleware_replaces_invalid_header(client):
    response = client.get("/health/live", HTTP_X_CORRELATION_ID="invalid value\n")
    assert uuid.UUID(response["X-Correlation-ID"])


def test_actor_context_is_derived_from_authenticated_identity():
    organisation = SimpleNamespace(pk=uuid.uuid4(), is_active=True)
    organisation_user = SimpleNamespace(
        pk=uuid.uuid4(), organisation=organisation, role="dispatcher", is_active=True
    )
    user = SimpleNamespace(
        pk=uuid.uuid4(), is_authenticated=True, organisation_user=organisation_user
    )
    request = SimpleNamespace(user=user)

    actor = resolve_actor(request)

    assert actor.organisation is organisation
    assert actor.role == "dispatcher"
    assert request.actor is actor


def test_inactive_organisation_context_is_rejected():
    organisation = SimpleNamespace(pk=uuid.uuid4(), is_active=False)
    organisation_user = SimpleNamespace(
        pk=uuid.uuid4(), organisation=organisation, role="owner", is_active=True
    )
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, organisation_user=organisation_user)
    )

    with pytest.raises(OrganisationContextError):
        resolve_actor(request)


def test_role_permission_uses_resolved_organisation_user_role():
    organisation = SimpleNamespace(pk=uuid.uuid4(), is_active=True)
    organisation_user = SimpleNamespace(
        pk=uuid.uuid4(), organisation=organisation, role="dispatcher", is_active=True
    )
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, organisation_user=organisation_user)
    )

    assert IsOwnerOrDispatcher().has_permission(request, view=None)
