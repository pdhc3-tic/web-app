"""Dataset consolidado do Plano de Trabalho para exportações e Power BI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.models import Activity, WorkPlanAcao
from apps.sgp.services.workplan_dashboard import enrich_dashboard_action


EXPORT_COLUMNS = (
    ("meta", "Meta"),
    ("acao", "Ação"),
    ("tipo_unidade", "Tipo/Unidade"),
    ("quantidade_planejada", "Quantidade planejada"),
    ("valor_unitario", "Valor unitário"),
    ("valor_total", "Valor total"),
    ("quantidade_realizada", "Quantidade realizada"),
    ("percentual_realizado", "Percentual realizado"),
    ("status_execucao", "Status de execução"),
    ("semaforo", "Semáforo"),
)


def workplan_export_rows(
    *,
    user=None,
    meta_id: int | None = None,
    territorio_id: int | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
) -> list[dict[str, str]]:
    """Retorna o dataset plano, com agregações calculadas no escopo permitido."""
    actions = _export_actions_for_scope(user=user, territorio_id=territorio_id)

    if meta_id is not None:
        actions = actions.filter(meta_id=meta_id)
    if periodo_inicio is not None:
        actions = actions.filter(
            Q(data_fim__gte=periodo_inicio)
            | Q(data_fim__isnull=True, meta__data_fim__gte=periodo_inicio)
        )
    if periodo_fim is not None:
        actions = actions.filter(
            Q(data_inicio__lte=periodo_fim)
            | Q(data_inicio__isnull=True, meta__data_inicio__lte=periodo_fim)
        )

    return [_serialize_action(enrich_dashboard_action(action)) for action in actions]


def _export_actions_for_scope(*, user, territorio_id: int | None) -> QuerySet[WorkPlanAcao]:
    """Restringe tanto as linhas quanto a contagem de execução à mesma visibilidade."""
    activity_filter = Q(atividades__ativo=True)
    visible_activities = Activity.objects.filter(acao_id=OuterRef("pk"), ativo=True)

    if user is not None:
        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            pass
        elif user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return WorkPlanAcao.objects.none()
            activity_filter &= Q(atividades__municipio__state__sigla__in=states)
            visible_activities = visible_activities.filter(
                municipio__state__sigla__in=states
            )
        elif user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            if not territories.exists():
                return WorkPlanAcao.objects.none()
            activity_filter &= Q(atividades__municipio__territory__in=territories)
            visible_activities = visible_activities.filter(
                municipio__territory__in=territories
            )
        else:
            raise PermissionDenied("Você não tem acesso ao Plano de Trabalho.")

    if territorio_id is not None:
        activity_filter &= Q(atividades__municipio__territory_id=territorio_id)
        visible_activities = visible_activities.filter(municipio__territory_id=territorio_id)

    actions = WorkPlanAcao.objects.select_related("meta").annotate(
        _quantidade_realizada=Count(
            "atividades",
            filter=activity_filter & Q(atividades__status="concluido"),
            distinct=True,
        )
    )

    # Ações sem atividade são visíveis somente para perfis com visão global.
    if user is not None and not (
        user_has_role(user, "super-admin") or user_has_role(user, "ugp")
    ):
        actions = actions.filter(Exists(visible_activities))
    elif territorio_id is not None:
        actions = actions.filter(Exists(visible_activities))

    return actions.order_by("meta__numero", "numero")


def _serialize_action(action: WorkPlanAcao) -> dict[str, str]:
    return {
        "meta": f"{action.meta.numero} - {action.meta.titulo}",
        "acao": f"{action.numero} - {action.descricao}",
        "tipo_unidade": action.get_tipo_unidade_display(),
        "quantidade_planejada": _decimal_string(action.quantidade_planejada),
        "valor_unitario": _decimal_string(action.valor_unitario),
        "valor_total": _decimal_string(action.valor_total),
        "quantidade_realizada": _decimal_string(action.dashboard_quantidade_realizada),
        "percentual_realizado": _decimal_string(action.dashboard_percentual_realizado),
        "status_execucao": action.dashboard_status_execucao,
        "semaforo": action.dashboard_semaforo,
    }


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
