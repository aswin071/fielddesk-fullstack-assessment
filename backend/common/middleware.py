import logging
import re
import time
import uuid

from common.context import reset_correlation_id, set_correlation_id

CORRELATION_HEADER = "X-Correlation-ID"
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
request_logger = logging.getLogger("fielddesk.request")


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get(CORRELATION_HEADER, "")
        correlation_id = (
            supplied if CORRELATION_ID_PATTERN.fullmatch(supplied) else str(uuid.uuid4())
        )
        request.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)
        try:
            response = self.get_response(request)
            response[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            reset_correlation_id(token)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            request_logger.exception(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.path,
                    "durationMs": round((time.monotonic() - started) * 1000, 2),
                },
            )
            raise

        actor = getattr(request, "actor", None)
        request_logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.path,
                "statusCode": response.status_code,
                "durationMs": round((time.monotonic() - started) * 1000, 2),
                "actorId": getattr(getattr(actor, "user", None), "pk", None),
                "organisationId": getattr(getattr(actor, "organisation", None), "pk", None),
            },
        )
        return response
