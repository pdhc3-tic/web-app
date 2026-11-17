"""Ciclo de vida do usuário que afeta outros módulos."""
from __future__ import annotations

import logging
from collections.abc import Iterable

from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context

audit_event_logger = logging.getLogger("audit_events")

SUPER_ADMIN = "super-admin"
TRAVA_DO_ULTIMO_SUPER_ADMIN = "core_ultimo_super_admin"
MENSAGEM_DO_ULTIMO_SUPER_ADMIN = "Este é o último Super Admin ativo: ative ou cadastre outro antes."


def _vinculos_que_operam():
    """Vínculos Super Admin de quem consegue entrar: ativo e sem acesso revogado."""
    from apps.core.models import UserProfile

    return UserProfile.objects.filter(perfil__slug=SUPER_ADMIN, user__ativo=True, user__acesso_revogado=False)


def sobra_super_admin(*, sem_usuarios: Iterable[int] = (), sem_vinculos: Iterable[int] = ()) -> bool:
    """Se, sem esses usuários e vínculos, ainda há Super Admin que opera; ou se eles não tiram nenhum, porque
    nenhum deles opera. Sem trava: sozinha, serve para decidir o que mostrar, não para gravar."""
    restantes = _vinculos_que_operam().exclude(user_id__in=sem_usuarios).exclude(pk__in=sem_vinculos)
    if restantes.exists():
        return True
    afetados = _vinculos_que_operam().filter(Q(user_id__in=sem_usuarios) | Q(pk__in=sem_vinculos))
    return not afetados.exists()


def exigir_super_admin_restante(
    *, sem_usuarios: Iterable[int] = (), sem_vinculos: Iterable[int] = (), campo: str = "ativo",
) -> None:
    """Recusa, com o erro em `campo`, tirar de operação os últimos Super Admins: desativar, revogar o
    acesso, tirar o perfil ou excluir. Vale para qualquer usuário ou vínculo, Super Admin ou não, porque
    saber se é Super Admin antes da trava abriria espaço para quem acabou de virar um.

    Um advisory lock único, pego antes de qualquer linha, serializa toda conferência até o commit, e a
    contagem é um comando depois dele, que já vê o que a transação anterior gravou. Fora de uma transação
    a trava não duraria até a gravação, por isso é recusado."""
    conexao = transaction.get_connection()
    if not conexao.in_atomic_block:
        raise TransactionManagementError("A conferência do último Super Admin precisa de uma transação.")
    with conexao.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [TRAVA_DO_ULTIMO_SUPER_ADMIN])
    if not sobra_super_admin(sem_usuarios=sem_usuarios, sem_vinculos=sem_vinculos):
        raise ValidationError({campo: [MENSAGEM_DO_ULTIMO_SUPER_ADMIN]})


@transaction.atomic
def desativar(user, *, por) -> list:
    """Desativa `user` preservando os dados e cancela as demandas não autorizadas dele,
    o que libera o saldo comprometido nelas. Devolve as demandas canceladas.

    Se uma demanda mudar durante a operação, `TransicaoInvalida` desfaz tudo, inclusive
    o `ativo` no banco; a instância em memória fica para quem chamou corrigir."""
    from apps.sgd.services.desativacao import cancelar_demandas_do_usuario

    if not user.ativo:
        return []
    if por is not None and por.pk == user.pk:
        raise ValidationError({"ativo": ["Você não pode desativar a própria conta."]})
    exigir_super_admin_restante(sem_usuarios=[user.pk])
    # Antes do cancelamento, para um Articulador desativado não notificar a si mesmo.
    # Só `ativo` muda, sem tocar em coluna referenciada: o lock não barra as checagens
    # de FK de quem grava notificação ou auditoria para este usuário.
    user.ativo = False
    user.save(update_fields=["ativo"])
    canceladas = cancelar_demandas_do_usuario(user, por=por)

    contexto = get_audit_context()
    log_audit(
        user=por,
        acao="user.deactivated",
        modulo="core",
        entidade="User",
        entidade_id=user.pk,
        valores_anteriores={"ativo": True},
        valores_novos={"ativo": False, "demandas_canceladas": [demand.pk for demand in canceladas]},
        _ip=contexto["ip"],
        _user_agent=contexto["user_agent"],
    )
    audit_event_logger.info(
        "user.deactivated actor_user_id=%s target_user_id=%s demandas_canceladas=%s",
        getattr(por, "pk", None),
        user.pk,
        len(canceladas),
    )
    return canceladas


def exigir_super_admin_nos_perfis(user, perfis_input: list[dict]) -> None:
    """Na troca dos perfis de `user`: sem o Super Admin na lista nova, confere que sobra outro."""
    from apps.core.models import Role

    super_admin = Role.objects.filter(slug=SUPER_ADMIN).values_list("pk", flat=True).first()
    if all(item["perfil_id"] != super_admin for item in perfis_input):
        exigir_super_admin_restante(sem_usuarios=[user.pk], campo="perfis_input")


def encerrar_sessoes(user) -> int:
    """Bloqueia os refresh tokens do usuário em todos os dispositivos. Devolve quantos foram bloqueados."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    encerradas = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, criado = BlacklistedToken.objects.get_or_create(token=token)
        encerradas += int(criado)
    return encerradas


def revogar_acesso(user, *, por) -> int:
    """Revoga o acesso de `user` e encerra as sessões dele, para o SCA fazer o wipe no próximo sync.
    Devolve quantas sessões foram encerradas. A gravação, as sessões e a auditoria entram ou saem
    juntas."""
    if por is not None and por.pk == user.pk:
        raise ValidationError({"acesso_revogado": ["Você não pode revogar o próprio acesso."]})
    with transaction.atomic():
        # Super Admin sem acesso não entra: revogar o último deixa o sistema sem quem reative contas.
        exigir_super_admin_restante(sem_usuarios=[user.pk], campo="acesso_revogado")
        user.acesso_revogado = True
        user.acesso_revogado_em = timezone.now()
        user.acesso_revogado_por = por
        user.save(update_fields=["acesso_revogado", "acesso_revogado_em", "acesso_revogado_por"])
        encerradas = encerrar_sessoes(user)
        contexto = get_audit_context()
        log_audit(
            user=por,
            acao="user.access_revoked",
            modulo="core",
            entidade="User",
            entidade_id=user.pk,
            valores_anteriores={"acesso_revogado": False},
            valores_novos={"acesso_revogado": True, "sessoes_invalidadas": encerradas},
            _ip=contexto["ip"],
            _user_agent=contexto["user_agent"],
        )
    audit_event_logger.info(
        "user.access_revoked actor_user_id=%s target_user_id=%s sessions=%s",
        getattr(por, "pk", None), user.pk, encerradas,
    )
    return encerradas
