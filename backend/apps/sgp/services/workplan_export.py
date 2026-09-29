"""Dataset consolidado do Plano de Trabalho para exportações e Power BI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Exists, OuterRef, QuerySet

from apps.sgp.models import Activity, WorkPlanAcao
from apps.sgp.models.workplan import arredondar, custo_unitario
from apps.sgp.services.apuracao import RecorteAtividades, filtro_de_atividades
from apps.sgp.services.budget import limiares_semaforo
from apps.sgp.services.workplan_access import is_global_workplan_user
from apps.sgp.services.workplan_dashboard import dashboard_actions, enrich_dashboard_action


EXPORT_COLUMNS = (
    ("meta", "Meta"),
    ("submeta_numero", "Número da Submeta"),
    ("submeta_titulo", "Título da Submeta"),
    ("acao", "Ação"),
    ("indicador", "Indicador"),
    ("unidade_medida", "Unidade de medida"),
    ("forma_apuracao", "Forma de apuração"),
    ("quantidade_planejada", "Quantidade planejada"),
    ("valor_unitario", "Valor unitário"),
    ("valor_total", "Valor total"),
    ("quantidade_realizada", "Quantidade realizada"),
    ("percentual_realizado", "Percentual realizado"),
    ("valor_executado", "Valor executado"),
    ("custo_unitario_realizado", "Custo unitário realizado"),
    ("saldo", "Saldo"),
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
        actions = actions.filter(data_fim__gte=periodo_inicio)
    if periodo_fim is not None:
        actions = actions.filter(data_inicio__lte=periodo_fim)

    limiares = limiares_semaforo()
    return [
        _serialize_action(enrich_dashboard_action(action, limiares=limiares))
        for action in actions
    ]


def _export_actions_for_scope(*, user, territorio_id: int | None) -> QuerySet[WorkPlanAcao]:
    """Restringe tanto as linhas quanto a apuração à mesma visibilidade."""
    filtro = filtro_de_atividades(user, RecorteAtividades(territorio_id=territorio_id))
    actions = dashboard_actions(filtro)

    # Ações sem atividade são visíveis somente para perfis com visão global.
    if (user is not None and not is_global_workplan_user(user)) or territorio_id is not None:
        visible_activities = Activity.objects.filter(acao_id=OuterRef("pk"))
        if filtro is not None:
            visible_activities = visible_activities.filter(filtro(""))
        actions = actions.filter(Exists(visible_activities))

    return actions.order_by("meta__numero", "submeta__numero", "numero")


def _serialize_action(action: WorkPlanAcao) -> dict[str, str]:
    valor_total = action.valor_total
    valor_executado = action.dashboard_valor_executado
    custo = custo_unitario(valor_executado, action.dashboard_quantidade_realizada)
    return {
        "meta": f"{action.meta.numero} - {action.meta.titulo}",
        "submeta_numero": action.submeta.numero,
        "submeta_titulo": action.submeta.titulo,
        "acao": f"{action.numero} - {action.descricao}",
        "indicador": f"{action.indicador.codigo} - {action.indicador.nome}",
        "unidade_medida": action.indicador.get_unidade_medida_display(),
        "forma_apuracao": action.indicador.get_forma_apuracao_display(),
        # Débito técnico: chave do antigo `tipo_unidade`, mantida só para o
        # dataset do Power BI, que lê as linhas por chave (as colunas do CSV e
        # do XLSX vêm de EXPORT_COLUMNS e não a incluem).
        "tipo_unidade": action.indicador.nome,
        "quantidade_planejada": _decimal_string(action.quantidade_planejada),
        "valor_unitario": _decimal_string(action.valor_unitario),
        "valor_total": _decimal_string(valor_total),
        "quantidade_realizada": _decimal_string(action.dashboard_quantidade_realizada),
        "percentual_realizado": _decimal_string(action.dashboard_percentual_realizado),
        "valor_executado": _decimal_string(valor_executado),
        "custo_unitario_realizado": "" if custo is None else _decimal_string(custo),
        "saldo": _decimal_string(arredondar(valor_total - valor_executado)),
        "status_execucao": action.dashboard_status_execucao,
        "semaforo": action.dashboard_semaforo,
    }


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
