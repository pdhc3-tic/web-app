"""Política de visibilidade territorial compartilhada pelo Plano de Trabalho."""

from django.db.models import Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.sgp.models import WorkPlanAcao, WorkPlanMeta
from apps.sgp.services.access import resolver_escopo


def is_global_workplan_user(user) -> bool:
    tipo, _ = resolver_escopo(user)
    return tipo == "global"


def activity_scope_for_user(user, *, prefix: str = "atividades__") -> Q | None:
    """Retorna o filtro de atividade do usuário, ou ``None`` para visão global."""
    tipo, valor = resolver_escopo(user)

    if tipo == "global":
        return None
    if tipo == "estados":
        return Q(
            **{
                f"{prefix}ativo": True,
                f"{prefix}municipio__state__sigla__in": valor,
            }
        )
    if tipo == "territorios":
        return Q(
            **{
                f"{prefix}ativo": True,
                f"{prefix}municipio__territory__in": valor,
            }
        )
    if tipo == "vazio":
        return Q(pk__in=[])

    raise PermissionDenied("Você não tem acesso ao Plano de Trabalho.")


def filter_workplan_actions_for_user(
    queryset: QuerySet[WorkPlanAcao], user
) -> QuerySet[WorkPlanAcao]:
    """Limita Ações às que têm ao menos uma atividade no escopo do usuário."""
    scope = activity_scope_for_user(user)
    if scope is None:
        return queryset
    return queryset.filter(scope).distinct()


def filter_workplan_metas_for_user(
    queryset: QuerySet[WorkPlanMeta], user
) -> QuerySet[WorkPlanMeta]:
    """Limita Metas às que possuem Ações visíveis para o usuário."""
    scope = activity_scope_for_user(user, prefix="acoes__atividades__")
    if scope is None:
        return queryset
    return queryset.filter(scope).distinct()
