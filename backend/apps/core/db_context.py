"""Contexto de acesso do PostgreSQL usado pelas políticas RLS.

As políticas leem variáveis de sessão (`app.current_user_id`, `app.user_role`,
`app.user_territorios` e `app.ufpa_sistema`). Elas são gravadas com
`set_config(..., true)`, que vale até o fim da transação externa: por isso tudo
aqui roda dentro de `transaction.atomic()`, e o valor anterior é devolvido no
fim do bloco. Se o bloco falhar, o rollback do savepoint já desfaz o
`set_config`, como em `apps.sgp.budget.rls.visao_total`.

O middleware HTTP (`SessionContextMiddleware`) e o que roda fora dele (tarefas
Celery, como a exportação assíncrona) montam o contexto pela mesma função,
`montar_contexto`.
"""
import logging
from contextlib import contextmanager

from django.db import connection, transaction

logger = logging.getLogger(__name__)

VARIAVEIS = ("app.current_user_id", "app.user_role", "app.user_territorios")
VARIAVEL_SISTEMA_UFPA = "app.ufpa_sistema"

# Só os papéis com critério próprio na política RLS de sgd_demand precisam
# entrar em `app.user_role` — qualquer outro papel cai no critério "vê as
# próprias" daquela policy. Mesma ordem de prioridade de
# apps.sgd.services.approval.demand_visibility_scope: super-admin/ugp/fgd dão
# acesso total, articulador-estadual é o único com recorte territorial.
# `adt-acr` não precisa estar aqui: a política de sgp_ufpa não lê
# `app.user_role`, resolve os perfis direto de `core_userprofile` a partir de
# `app.current_user_id` (ver apps/sgp/migrations/0022_rls_ufpa.py).
ROLES_RLS = ("super-admin", "ugp", "fgd", "articulador-estadual")


def montar_contexto(user, token=None) -> dict:
    """Contexto de banco do usuário. `token` (JWT) é opcional: se trouxer role
    ou territórios, eles têm precedência sobre o banco."""
    token = token or {}
    # O JWT emitido hoje (setup/serializers.py:LoginSerializer) não carrega
    # role/perfil/território — só user_id. Sem o fallback pro banco, toda
    # política baseada em app.user_role/app.user_territorios trataria
    # UGP/FGD/Articulador como se não tivessem papel nenhum.
    role = str(token.get("role") or token.get("perfil") or "") or _role_do_banco(user)
    territorios = _formatar_territorios(token.get("territorios")) or _territorios_do_banco(user)
    user_id = token.get("user_id") or user.pk
    return {"user_id": str(user_id), "territorios": territorios, "role": role}


def contexto_de_admin(user) -> dict:
    """Sessão do Django Admin (cookie, não JWT): só superusuário é staff."""
    return {"user_id": str(user.pk), "territorios": "", "role": "super-admin"}


def _role_do_banco(user) -> str:
    try:
        from apps.core.services.permissions import user_role_slugs
        slugs = user_role_slugs(user, slugs=ROLES_RLS)
    except Exception:
        # Fail-safe: role vazio nunca é um dos papéis privilegiados, então isso
        # só restringe — mas um lookup de RLS falhando em silêncio não pode
        # passar despercebido.
        logger.exception("session_context.user_role_from_db_failed user_id=%s", getattr(user, "pk", None))
        return ""
    for role in ROLES_RLS:
        if role in slugs:
            return role
    return ""


def _territorios_do_banco(user) -> str:
    try:
        from apps.core.models.user_profile import UserProfile
        ids = list(
            UserProfile.objects.filter(user=user, territorio__isnull=False).values_list("territorio_id", flat=True)
        )
        return ",".join(str(i) for i in ids) if ids else ""
    except Exception:
        logger.exception("session_context.user_territories_from_db_failed user_id=%s", getattr(user, "pk", None))
    return ""


def _formatar_territorios(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (list, tuple, set)):
        return ",".join(str(territorio_id) for territorio_id in raw)
    return str(raw)


def aplicar_contexto(contexto: dict) -> None:
    """Grava o contexto na transação corrente. Sempre zera a elevação de
    sistema da UFPA: um contexto de usuário nunca herda uma elevação."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_user_id', %s, true)", [contexto["user_id"]])
        cursor.execute("SELECT set_config('app.user_territorios', %s, true)", [contexto["territorios"]])
        cursor.execute("SELECT set_config('app.user_role', %s, true)", [contexto["role"]])
        cursor.execute("SELECT set_config(%s, '', true)", [VARIAVEL_SISTEMA_UFPA])


def _ler(variaveis) -> dict:
    with connection.cursor() as cursor:
        valores = {}
        for nome in variaveis:
            cursor.execute("SELECT current_setting(%s, true)", [nome])
            valores[nome] = cursor.fetchone()[0] or ""
        return valores


def _restaurar(valores: dict) -> None:
    with connection.cursor() as cursor:
        for nome, valor in valores.items():
            cursor.execute("SELECT set_config(%s, %s, true)", [nome, valor])


@contextmanager
def contexto_de_acesso(user):
    """Executa o bloco com o contexto RLS de `user` — para o que roda fora do
    middleware HTTP (tarefas Celery). Restaura o contexto anterior no fim."""
    with transaction.atomic():
        anteriores = _ler((*VARIAVEIS, VARIAVEL_SISTEMA_UFPA))
        aplicar_contexto(montar_contexto(user))
        yield
        _restaurar(anteriores)


@contextmanager
def acesso_de_sistema_ufpa(motivo: str):
    """Libera `sgp_ufpa` inteira para uma operação de sistema já autorizada em
    Python (ex.: checagem de duplicidade do SCA). Não altera `app.user_role`,
    então não amplia o acesso a nenhuma outra tabela. Use no menor bloco
    possível."""
    with transaction.atomic():
        anterior = _ler((VARIAVEL_SISTEMA_UFPA,))
        logger.info("rls.ufpa_sistema motivo=%s", motivo)
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config(%s, 'on', true)", [VARIAVEL_SISTEMA_UFPA])
        yield
        _restaurar(anterior)
