import logging

from django.db import connection, transaction
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from apps.core.db_context import ROLES_RLS, contexto_de_admin, montar_contexto
from apps.core.signals.audit import set_audit_context, clear_audit_context
from apps.core.utils import get_client_ip


logger = logging.getLogger(__name__)


# Prefixo antigo → rota canônica. Ficam ativos por um ciclo, até o front migrar.
ROTAS_DEPRECIADAS = {
    "/api/v1/sgp/upfs/": "/api/v1/sgp/ufpas/",
    "/api/v1/upfs/": "/api/v1/sgp/ufpas/",
}


class RotaDepreciadaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        for prefixo, canonica in ROTAS_DEPRECIADAS.items():
            if request.path.startswith(prefixo):
                response["Deprecation"] = "true"
                response["Link"] = f'<{canonica}{request.path[len(prefixo):]}>; rel="successor-version"'
                break
        return response


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
    # Montagem do contexto em apps.core.db_context — a mesma usada fora do
    # HTTP (tarefas Celery). Ver lá por que `adt-acr` não está em ROLES_RLS.
    _ROLES_RLS = ROLES_RLS

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()

    def __call__(self, request):
        auth_result = self._authenticate_request(request)
        is_authenticated = bool(getattr(request.user, "is_authenticated", False))

        if auth_result is not None and is_authenticated:
            _, token = auth_result
            context = self._build_session_context(token, request.user)
        elif (
            request.path.startswith("/admin/")
            and is_authenticated
            and getattr(request.user, "is_staff", False)
        ):
            # Sessão do Django (cookie, não JWT) especificamente no Admin
            # (setup/urls.py: path("admin/", ...)) — sem restringir por path,
            # qualquer request com cookie de sessão de staff (ex.: a mesma
            # aba do navegador batendo na API depois de logar no Admin)
            # cairia aqui também. Quem chega até aqui já passou pelo próprio
            # gate do Django (is_staff, que nesse User model só é True pra
            # superusuário) — trata como acesso total pra RLS. Sem isso, RLS
            # (sgd_demand e futuras tabelas) deixa o Admin com listas vazias
            # pra qualquer staff, já que superusuário do Django não tem
            # nenhuma relação com privilégio de role no Postgres.
            context = contexto_de_admin(request.user)
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

    def _build_session_context(self, token, user):
        return montar_contexto(user, token)

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

    @staticmethod
    def _set_database_session_context(context):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_user_id = %s;", [context["user_id"]])
            cursor.execute("SET LOCAL app.user_territorios = %s;", [context["territorios"]])
            cursor.execute("SET LOCAL app.user_role = %s;", [context["role"]])


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

        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        set_audit_context(user=user, ip=ip, user_agent=user_agent)
        try:
            response = self.get_response(request)
        finally:
            clear_audit_context()

        return response
