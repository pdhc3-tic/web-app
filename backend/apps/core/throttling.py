from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class CustomWindowRateThrottle(SimpleRateThrottle):
    def parse_rate(self, rate):
        if rate is None:
            return None, None

        num, period = rate.split("/")
        return int(num), self._parse_duration(period)

    def _parse_duration(self, period):
        multipliers = {
            "s": 1,
            "sec": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
        }
        amount = ""
        unit = ""

        for char in period:
            if char.isdigit():
                amount += char
            else:
                unit += char

        return int(amount or 1) * multipliers[unit]
    
    def get_cache_key(self, request, view):
        return f"throttle_{self.scope}_{self.get_ident(request)}"


class LoginRateThrottle(CustomWindowRateThrottle):
    scope = "auth_login"


class RefreshRateThrottle(CustomWindowRateThrottle):
    scope = "auth_refresh"


class PasswordResetByIPThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_ip"


class PasswordResetByEmailThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return None
        return f"throttle_{self.scope}_{email}"


class PasswordResetConfirmThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_confirm"


class NotificationUnreadCountThrottle(UserRateThrottle):
    scope = "notification_unread_count"
