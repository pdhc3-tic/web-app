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
    # Só os papéis com critério próprio na política RLS de sgd_demand
    # precisam de resolução aqui — qualquer outro papel cai no critério
    # "vê as próprias" da policy, que não olha pra app.user_role. Mesma
    # ordem de prioridade de apps.sgd.services.approval.demand_visibility_scope:
    # super-admin/ugp/fgd dão acesso total (a ordem entre os três não importa
    # pro resultado), articulador-estadual é o único com recorte territorial.
    _ROLES_RLS = ("super-admin", "ugp", "fgd", "articulador-estadual")

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

    def _build_session_context(self, token, user):
        # O JWT emitido hoje (setup/serializers.py:LoginSerializer, um
        # TokenObtainPairSerializer sem get_token() customizado) não carrega
        # role/perfil/território nenhum — só user_id. Sem o fallback pro
        # banco aqui, toda política RLS baseada em app.user_role/
        # app.user_territorios trataria UGP/FGD/Articulador como se não
        # tivessem papel nenhum, e cada um só veria as próprias demandas.
        role = str(token.get("role") or token.get("perfil") or "") or self._user_role_from_db(user)
        territorios = self._format_territorios(token.get("territorios")) or self._user_territories_from_db(user)
        return {
            "user_id": str(token["user_id"]),
            "territorios": territorios,
            "role": role,
        }

    @classmethod
    def _user_role_from_db(cls, user):
        try:
            from apps.core.services.permissions import user_role_slugs
            slugs = user_role_slugs(user, slugs=cls._ROLES_RLS)
        except Exception:
            # Fail-safe: role vazio nunca é um dos papéis privilegiados na
            # policy, então isso só restringe (cai no "vê as próprias"),
            # nunca abre acesso — mas logamos, porque essa mesma forma de
            # engolir exceção em silêncio foi o que escondeu o bug original.
            logger.exception("session_context.user_role_from_db_failed user_id=%s", getattr(user, "pk", None))
            return ""
        for role in cls._ROLES_RLS:
            if role in slugs:
                return role
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
            # Ao contrário do role, "" aqui significa "todos os territórios"
            # pra um Articulador (fail-open) — mas só importa se o role
            # também resolveu pra articulador-estadual; se a mesma falha
            # atingiu os dois lookups, o role já veio "" e essa policy nem
            # olha pro território. Loga pra não repetir o silêncio que
            # escondeu o bug original.
            logger.exception("session_context.user_territories_from_db_failed user_id=%s", getattr(user, "pk", None))
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
