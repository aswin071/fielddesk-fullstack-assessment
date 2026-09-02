from rest_framework.throttling import UserRateThrottle


class ProgressEventThrottle(UserRateThrottle):
    scope = "progress_event"

