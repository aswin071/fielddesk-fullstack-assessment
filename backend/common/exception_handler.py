import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.context import get_correlation_id

logger = logging.getLogger("fielddesk.api")


def _error_code(detail, fallback: str) -> str:
    if isinstance(detail, ErrorDetail):
        return str(detail.code).upper()
    if isinstance(detail, dict):
        for value in detail.values():
            return _error_code(value, fallback)
    if isinstance(detail, (list, tuple)) and detail:
        return _error_code(detail[0], fallback)
    return fallback


def _field_errors(detail):
    if not isinstance(detail, dict):
        return {}
    errors = {}
    for field, value in detail.items():
        if isinstance(value, (list, tuple)):
            errors[field] = [str(item) for item in value]
        elif isinstance(value, dict):
            errors[field] = _field_errors(value)
        else:
            errors[field] = [str(value)]
    return errors


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    correlation_id = get_correlation_id()

    if response is None:
        logger.exception(
            "unhandled_api_exception",
            exc_info=exc,
            extra={"event": "unhandled_api_exception"},
        )
        return Response(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "fields": {},
                    "correlationId": correlation_id,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = (
        response.data.get("detail", response.data)
        if isinstance(response.data, dict)
        else response.data
    )
    if isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = "The submitted data is invalid."
        fields = _field_errors(detail)
    else:
        fallback = "REQUEST_ERROR"
        if isinstance(exc, (Http404,)):
            fallback = "NOT_FOUND"
        elif isinstance(exc, DjangoPermissionDenied):
            fallback = "PERMISSION_DENIED"
        code = _error_code(detail, getattr(exc, "default_code", fallback)).upper()
        message = (
            str(detail)
            if not isinstance(detail, (dict, list))
            else str(getattr(exc, "detail", "Request failed."))
        )
        fields = {}

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "fields": fields,
            "correlationId": correlation_id,
        }
    }
    return response
