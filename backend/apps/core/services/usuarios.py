"""Ciclo de vida do usuário que afeta outros módulos."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context

audit_event_logger = logging.getLogger("audit_events")

SUPER_ADMIN = "super-admin"


def e_super_admin(user) -> bool:
    from apps.core.models import UserProfile

    return UserProfile.objects.filter(user=user, perfil__slug=SUPER_ADMIN).exists()


def _vinculos_que_operam():
    """Vínculos Super Admin de quem consegue entrar: ativo e sem acesso revogado."""
    from apps.core.models import UserProfile

    return UserProfile.objects.filter(perfil__slug=SUPER_ADMIN, user__ativo=True, user__acesso_revogado=False)


def travar_super_admins() -> None:
    """Trava, em ordem de pk, a linha de todo usuário com o perfil Super Admin. Vem antes de qualquer
    outra linha de usuário, para quem tira um Super Admin conferir depois de quem tirou outro."""
    from apps.core.models import User, UserProfile

    list(
        User.objects.select_for_update(no_key=True)
        .filter(pk__in=UserProfile.objects.filter(perfil__slug=SUPER_ADMIN).values("user_id"))
        .order_by("pk").values_list("pk", flat=True)
    )


def sobra_super_admin(*, sem_usuarios=(), sem_vinculos=()) -> bool:
    """Se, sem esses usuários e vínculos, ainda há Super Admin que opera; ou se eles não tiram nenhum, porque
    nenhum deles opera. Sem trava: serve para decidir o que mostrar, não para gravar."""
    restantes = _vinculos_que_operam().exclude(user_id__in=sem_usuarios).exclude(pk__in=sem_vinculos)
    if restantes.exists():
        return True
    afetados = _vinculos_que_operam().filter(Q(user_id__in=sem_usuarios) | Q(pk__in=sem_vinculos))
    return not afetados.exists()


def exigir_super_admin_restante(*, sem_usuarios=(), sem_vinculos=(), campo="ativo") -> None:
    """Recusa, com o erro em `campo`, tirar os últimos Super Admins que operam. A contagem é um comando
    depois da trava: o snapshot do comando que trava é de antes de esperar, e não veria o vínculo que a
    outra transação apagou ou o acesso que ela revogou. Quem chama está numa transação."""
    travar_super_admins()
    if not sobra_super_admin(sem_usuarios=sem_usuarios, sem_vinculos=sem_vinculos):
        raise ValidationError({campo: ["Este é o último Super Admin ativo: ative ou cadastre outro antes."]})


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
    if e_super_admin(user):
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
