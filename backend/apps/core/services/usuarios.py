"""Ciclo de vida do usuário que afeta outros módulos."""
from __future__ import annotations

import logging

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context

audit_event_logger = logging.getLogger("audit_events")

SUPER_ADMIN = "super-admin"


def e_super_admin(user) -> bool:
    from apps.core.models import UserProfile

    return UserProfile.objects.filter(user=user, perfil__slug=SUPER_ADMIN).exists()


def exigir_outro_super_admin_ativo(user) -> None:
    """Recusa tirar `user` dos Super Admins ativos se ele for o último. Trava os Super Admins ativos em
    ordem de pk antes de contar: dois pedidos simultâneos, cada um tirando um dos dois últimos, não
    passam juntos. Chamar antes de travar qualquer outra linha de usuário."""
    from apps.core.models import User, UserProfile

    ativos = list(
        User.objects.select_for_update(no_key=True)
        .filter(ativo=True, pk__in=UserProfile.objects.filter(perfil__slug=SUPER_ADMIN).values("user_id"))
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if ativos == [user.pk]:
        raise ValidationError({"ativo": "Este é o último Super Admin ativo: ative ou cadastre outro antes."})


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
        raise ValidationError({"ativo": "Você não pode desativar a própria conta."})
    if e_super_admin(user):
        exigir_outro_super_admin_ativo(user)
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
