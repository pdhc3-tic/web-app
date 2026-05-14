from rest_framework.throttling import SimpleRateThrottle


class PasswordResetByIPThrottle(SimpleRateThrottle):
    scope = "auth_password_reset_ip"

    def get_cache_key(self, request, view):
        return f"throttle_auth_password_reset_ip_{self.get_ident(request)}"

class PasswordResetByEmailThrottle(SimpleRateThrottle):
    scope = "auth_password_reset_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        if not email:
            return None
        return f"throttle_auth_password_reset_email_{email.lower()}"