import hashlib

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class LoginIpThrottle(AnonRateThrottle):
    scope = "auth_login_ip"


class LoginIdentityThrottle(SimpleRateThrottle):
    scope = "auth_login_identity"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return None
        digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}

