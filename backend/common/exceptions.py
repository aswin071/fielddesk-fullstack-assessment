from rest_framework import status
from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with current resource state."
    default_code = "CONFLICT"


class OrganisationContextError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "No active organisation access is available."
    default_code = "ORGANISATION_ACCESS_DENIED"


class ScheduleConflictError(ConflictError):
    default_detail = "The technician is unavailable during this period."
    default_code = "SCHEDULE_CONFLICT"


class IdempotencyKeyReusedError(ConflictError):
    default_detail = "The event ID was already used for a different request."
    default_code = "IDEMPOTENCY_KEY_REUSED"


class StorageQuotaExceededError(ConflictError):
    default_detail = "The organisation storage limit would be exceeded."
    default_code = "STORAGE_QUOTA_EXCEEDED"


class ExportTooLargeError(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The filtered export exceeds the configured row limit."
    default_code = "EXPORT_TOO_LARGE"
