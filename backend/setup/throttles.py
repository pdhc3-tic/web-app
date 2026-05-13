from rest_framework.throttling import SimpleRateThrottle


class PasswordResetByIPThrottle(SimpleRateThrottle):
    scope = "password_reset_ip"
    rate = "5/hour"

    def get_cache_key(self, request, view):
        return f"throttle_password_reset_ip_{self.get_ident(request)}"

class PasswordResetByEmailThrottle(SimpleRateThrottle):
    scope = "password_reset_email"
    rate = "3/hour"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        if not email:
            return None
        return f"throttle_password_reset_email_{email.lower()}"