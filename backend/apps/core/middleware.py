from django.db import connection, transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from apps.core.signals.audit import set_audit_context, clear_audit_context


class SessionContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTStatelessUserAuthentication()

    def __call__(self, request):
        auth_result = self._authenticate_request(request)
        is_authenticated = bool(getattr(request.user, "is_authenticated", False))
        if auth_result is None or not is_authenticated:
            return self.get_response(request)

        _, token = auth_result
        user_id = token["user_id"]
        user = request.user

        territorios = self._format_territorios(
            token.get("territorios") or self._user_territories_from_db(user)
        )
        role = str(
            token.get("role")
            or token.get("perfil")
            or self._user_role_from_db(user)
            or ""
        )

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_user_id = %s;", [str(user_id)])
                cursor.execute("SET LOCAL app.user_territorios = %s;", [territorios])
                cursor.execute("SET LOCAL app.user_role = %s;", [role])
            return self.get_response(request)

    @staticmethod
    def _user_role_from_db(user):
        try:
            from apps.core.models.user_profile import UserProfile
            profile = UserProfile.objects.filter(user=user).select_related("perfil").first()
            if profile:
                return profile.perfil.slug
        except Exception:
            pass
        return ""

    @staticmethod
    def _user_territories_from_db(user):
        try:
            from apps.core.models.user_profile import UserProfile
            ids = list(
                UserProfile.objects.filter(
                    user=user, territorio__isnull=False
                ).values_list("territorio_id", flat=True)
            )
            return ",".join(str(i) for i in ids) if ids else ""
        except Exception:
            pass
        return ""

    def _authenticate_request(self, request):
        try:
            auth_result = self.jwt_authentication.authenticate(request)
        except (AuthenticationFailed, InvalidToken, TokenError):
            return None

        if auth_result is None:
            return None

        request.user, request.auth = auth_result
        return auth_result

    @staticmethod
    def _format_territorios(raw_territorios):
        if raw_territorios is None:
            return ""
        if isinstance(raw_territorios, str):
            return raw_territorios
        if isinstance(raw_territorios, (list, tuple, set)):
            return ",".join(str(territorio_id) for territorio_id in raw_territorios)
        return str(raw_territorios)
    
class AuditContextMiddleware:
    """
    Injeta user, ip e user_agent num threading.local() para que os
    signals de auditoria possam acessar o contexto do request.
    Ações via shell/management command que não passam por aqui
    geram log com user=None e ip=null sem causar crash.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and not user.is_authenticated:
            user = None

        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        )
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        set_audit_context(user=user, ip=ip, user_agent=user_agent)
        try:
            response = self.get_response(request)
        finally:
            clear_audit_context()

        return response
