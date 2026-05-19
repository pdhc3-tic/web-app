from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    scope = "auth_login"
    rate = "5/min"  # explícito — evita silêncio se não for encontrado no settings. Deixar comentado.

    def get_cache_key(self, request, view):
        return f"throttle_login_{self.get_ident(request)}"


class NotificationUnreadCountThrottle(UserRateThrottle):
    scope = "notification_unread_count"