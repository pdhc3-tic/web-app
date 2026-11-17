"""Ciclo de vida do usuário que afeta outros módulos."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.db.models import Q
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


def sobra_super_admin(*, sem_usuarios=(), sem_vinculos=()) -> bool:
    """Se, sem esses usuários e vínculos, ainda há Super Admin que opera; ou se eles não tiram nenhum, porque
    nenhum deles opera. Sem trava: sozinha, serve para decidir o que mostrar, não para gravar."""
    restantes = _vinculos_que_operam().exclude(user_id__in=sem_usuarios).exclude(pk__in=sem_vinculos)
    if restantes.exists():
        return True
    afetados = _vinculos_que_operam().filter(Q(user_id__in=sem_usuarios) | Q(pk__in=sem_vinculos))
    return not afetados.exists()


def exigir_super_admin_restante(*, sem_usuarios=(), sem_vinculos=(), campo="ativo") -> None:
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
