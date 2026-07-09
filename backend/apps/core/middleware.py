import logging

from django.db import connection, transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from apps.core.signals.audit import set_audit_context, clear_audit_context


logger = logging.getLogger(__name__)


class SessionContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()

    def __call__(self, request):
        auth_result = self._authenticate_request(request)
        is_authenticated = bool(getattr(request.user, "is_authenticated", False))
        if auth_result is None or not is_authenticated:
            return self.get_response(request)

        _, token = auth_result
        context = self._build_session_context(token)

        # SET LOCAL only survives inside the current database transaction.
        with transaction.atomic():
            try:
                self._set_database_session_context(context)
            except Exception:
                logger.exception("session_context.set_local_failed user_id=%s", context["user_id"])
                raise
            return self.get_response(request)

    def _authenticate_request(self, request):
        try:
            auth_result = self.jwt_authentication.authenticate(request)
        except (AuthenticationFailed, InvalidToken, TokenError) as exc:
            logger.debug("session_context.jwt_authentication_failed error=%s", exc.__class__.__name__)
            return None

        if auth_result is None:
            return None

        request.user, request.auth = auth_result
        return auth_result

    def _build_session_context(self, token):
        return {
            "user_id": str(token["user_id"]),
            "territorios": self._format_territorios(token.get("territorios", [])),
            "role": str(token.get("role") or token.get("perfil") or ""),
        }

    @staticmethod
    def _set_database_session_context(context):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_user_id = %s;", [context["user_id"]])
            cursor.execute("SET LOCAL app.user_territorios = %s;", [context["territorios"]])
            cursor.execute("SET LOCAL app.user_role = %s;", [context["role"]])

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
