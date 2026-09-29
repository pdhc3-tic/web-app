"""Política de visibilidade territorial compartilhada pelo Plano de Trabalho."""

from django.db.models import Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta
from apps.sgp.services.access import resolver_escopo


def exigir_leitura_do_plano(user) -> tuple:
    """Escopo com que o usuário lê o Plano de Trabalho; 403 para quem não o lê.

    Pela matriz de permissões do Core (§2.1), o FGD lê o Plano de Trabalho,
    as Metas e Submetas e o catálogo de Indicadores. Ele não tem papel com
    escopo territorial, então lê tudo."""
    tipo, valor = resolver_escopo(user)
    if tipo == "negado" and user_has_role(user, "fgd"):
        return "global", None
    if tipo == "negado":
        raise PermissionDenied("Você não tem acesso ao Plano de Trabalho.")
    return tipo, valor


def is_global_workplan_user(user) -> bool:
    tipo, _ = exigir_leitura_do_plano(user)
    return tipo == "global"


def activity_scope_for_user(user, *, prefix: str = "atividades__") -> Q | None:
    """Retorna o filtro de atividade do usuário, ou ``None`` para visão global."""
    tipo, valor = exigir_leitura_do_plano(user)

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
    # "vazio": tem o papel com escopo, mas nenhum território ou estado.
    return Q(pk__in=[])


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


def filter_workplan_submetas_for_user(
    queryset: QuerySet[WorkPlanSubmeta], user
) -> QuerySet[WorkPlanSubmeta]:
    """Limita Submetas às que possuem Ações visíveis para o usuário."""
    scope = activity_scope_for_user(user, prefix="acoes__atividades__")
    if scope is None:
        return queryset
    return queryset.filter(scope).distinct()
