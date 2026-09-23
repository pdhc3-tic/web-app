import logging

from django.db import connection, transaction
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from apps.core.signals.audit import set_audit_context, clear_audit_context


logger = logging.getLogger(__name__)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "Content-Security-Policy" not in response:
            connect_src = " ".join(settings.CSP_CONNECT_SRC)
            response["Content-Security-Policy"] = f"connect-src {connect_src};"
        return response


class SessionContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()

    def __call__(self, request):
        auth_result = self._authenticate_request(request)
        is_authenticated = bool(getattr(request.user, "is_authenticated", False))

        if auth_result is not None and is_authenticated:
            _, token = auth_result
            context = self._build_session_context(token)
        elif is_authenticated and getattr(request.user, "is_staff", False):
            # Sessão do Django (ex.: /admin/), não JWT — AuthenticationMiddleware
            # já rodou antes (settings.MIDDLEWARE) e populou request.user pelo
            # cookie de sessão, mas não há token JWT pra extrair role/território
            # daqui. Quem chega até aqui já passou pelo próprio gate do Django
            # (is_staff) — trata como acesso total pra RLS, a mesma política que
            # já libera "ugp"/"fgd"/"super-admin". Sem isso, RLS (apps.sgd
            # sgd_demand e futuras tabelas) deixa o Admin com listas vazias pra
            # qualquer staff, já que superusuário do Django não tem nenhuma
            # relação com privilégio de role no Postgres.
            context = {"user_id": str(request.user.pk), "territorios": "", "role": "super-admin"}
        else:
            return self.get_response(request)

        # SET LOCAL only survives inside the current database transaction.
        with transaction.atomic():
            try:
                self._set_database_session_context(context)
            except Exception:
                logger.exception("session_context.set_local_failed user_id=%s", context["user_id"])
                raise
            return self.get_response(request)

    @staticmethod
    def _build_session_context(token):
        return {
            "user_id": token.get("user_id"),
            "territorios": token.get("territorios"),
            "role": token.get("role") or token.get("perfil"),
        }

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
