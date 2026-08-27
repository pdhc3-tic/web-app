"""Política de visibilidade territorial compartilhada pelo Plano de Trabalho."""

from django.db.models import Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta


def is_global_workplan_user(user) -> bool:
    return user_has_role(user, "super-admin") or user_has_role(user, "ugp")


def activity_scope_for_user(user, *, prefix: str = "atividades__") -> Q | None:
    """Retorna o filtro de atividade do usuário, ou ``None`` para visão global."""
    if is_global_workplan_user(user):
        return None

    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        if not states:
            return Q(pk__in=[])
        return Q(
            **{
                f"{prefix}ativo": True,
                f"{prefix}municipio__state__sigla__in": states,
            }
        )

    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        if not territories.exists():
            return Q(pk__in=[])
        return Q(
            **{
                f"{prefix}ativo": True,
                f"{prefix}municipio__territory__in": territories,
            }
        )

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
