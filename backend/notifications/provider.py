from dataclasses import dataclass

from django.conf import settings


class TemporaryProviderError(Exception):
    pass


class PermanentProviderError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ProviderResult:
    reference: str


class MockNotificationProvider:
    def send_assignment(self, *, delivery, attempt_number):
        mode = settings.NOTIFICATION_PROVIDER_MODE
        if mode == "success":
            return ProviderResult(reference=f"mock-{delivery.provider_idempotency_key}")
        if mode == "temporary_failure":
            raise TemporaryProviderError("Mock provider is temporarily unavailable.")
        if mode == "temporary_then_success":
            if attempt_number <= settings.NOTIFICATION_PROVIDER_TEMPORARY_FAILURES:
                raise TemporaryProviderError("Mock provider is temporarily unavailable.")
            return ProviderResult(reference=f"mock-{delivery.provider_idempotency_key}")
        if mode == "permanent_failure":
            raise PermanentProviderError("Mock provider rejected the destination permanently.")
        raise PermanentProviderError("Notification provider mode is invalid.")


def get_notification_provider():
    return MockNotificationProvider()
