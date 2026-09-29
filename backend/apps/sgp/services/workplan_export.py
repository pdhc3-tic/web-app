"""Dataset consolidado do Plano de Trabalho para exportações e Power BI.

O CSV e o XLSX exportam a árvore completa (SGP §5.6, RF25): uma linha por
Meta, Submeta e Ação, cada nó com o seu consolidado. O Power BI (RF26) recebe
só as linhas de Ação, para que as somas do BI não contem cada valor três vezes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Exists, OuterRef, QuerySet

from apps.sgp.models import Activity, WorkPlanAcao, WorkPlanMeta
from apps.sgp.models.workplan import arredondar, custo_unitario
from apps.sgp.services.apuracao import RecorteAtividades, filtro_de_atividades
from apps.sgp.services.budget import LimiaresSemaforo, limiares_semaforo
from apps.sgp.services.workplan_access import is_global_workplan_user
from apps.sgp.services.workplan_dashboard import (
    NodeSummary,
    dashboard_actions,
    enrich_dashboard_action,
    summarize_meta,
    summarize_node,
)


EXPORT_COLUMNS = (
    ("nivel", "Nível"),
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


def workplan_export_rows(*, user=None) -> list[dict[str, str]]:
    """Linhas de Ação (dataset do Power BI), com agregações no escopo permitido."""
    acoes, _ = _acoes_exportadas(user=user)
    return [_serialize_action(acao) for acao in acoes]


def workplan_export_tree_rows(
    *,
    user=None,
    meta_id: int | None = None,
    territorio_id: int | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
) -> list[dict[str, str]]:
    """Árvore completa para o CSV e o XLSX: cada Meta, cada Submeta dela e as
    Ações, nessa ordem. Sem recorte (visão global, sem território nem período),
    Metas e Submetas ainda sem Ações também aparecem."""
    acoes, limiares = _acoes_exportadas(
        user=user, meta_id=meta_id, territorio_id=territorio_id,
        periodo_inicio=periodo_inicio, periodo_fim=periodo_fim,
    )
    por_submeta = defaultdict(list)
    for acao in acoes:
        por_submeta[acao.submeta_id].append(acao)
    completa = (
        (user is None or is_global_workplan_user(user))
        and territorio_id is None and periodo_inicio is None and periodo_fim is None
    )

    metas = WorkPlanMeta.objects.prefetch_related("submetas")
    if meta_id is not None:
        metas = metas.filter(pk=meta_id)
    if not completa:
        metas = metas.filter(pk__in={acao.meta_id for acao in acoes})

    hoje = date.today()
    linhas = []
    for meta in metas:
        submetas = [s for s in meta.submetas.all() if completa or s.pk in por_submeta]
        consolidados = [summarize_node(por_submeta[s.pk], s, hoje, limiares) for s in submetas]
        acoes_da_meta = [acao for submeta in submetas for acao in por_submeta[submeta.pk]]
        linhas.append(_serialize_node(
            "Meta", meta, None, summarize_meta(acoes_da_meta, meta, consolidados, hoje, limiares)
        ))
        for submeta, consolidado in zip(submetas, consolidados):
            linhas.append(_serialize_node("Submeta", meta, submeta, consolidado))
            linhas.extend(_serialize_action(acao) for acao in por_submeta[submeta.pk])
    return linhas


def _acoes_exportadas(
    *,
    user=None,
    meta_id: int | None = None,
    territorio_id: int | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
) -> tuple[list[WorkPlanAcao], LimiaresSemaforo]:
    """Ações do escopo, já com os indicadores do painel, na ordem do model
    (Meta e número)."""
    actions = _export_actions_for_scope(user=user, territorio_id=territorio_id)

    if meta_id is not None:
        actions = actions.filter(meta_id=meta_id)
    if periodo_inicio is not None:
        actions = actions.filter(data_fim__gte=periodo_inicio)
    if periodo_fim is not None:
        actions = actions.filter(data_inicio__lte=periodo_fim)

    limiares = limiares_semaforo()
    acoes = [enrich_dashboard_action(action, limiares=limiares) for action in actions]
    return acoes, limiares


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

    return actions


def _serialize_action(action: WorkPlanAcao) -> dict[str, str]:
    valor_total = action.valor_total
    valor_executado = action.dashboard_valor_executado
    custo = custo_unitario(valor_executado, action.dashboard_quantidade_realizada)
    return {
        "nivel": "Ação",
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


def _serialize_node(nivel: str, meta, submeta, consolidado: NodeSummary) -> dict[str, str]:
    """Linha de Meta ou Submeta: o consolidado do nó; os campos que só existem
    na Ação (Indicador, valor e custo unitários) ficam vazios."""
    return {
        "nivel": nivel,
        "meta": f"{meta.numero} - {meta.titulo}",
        "submeta_numero": submeta.numero if submeta else "",
        "submeta_titulo": submeta.titulo if submeta else "",
        "acao": "",
        "indicador": "",
        "unidade_medida": "",
        "forma_apuracao": "",
        "quantidade_planejada": _decimal_string(arredondar(consolidado.quantidade_planejada)),
        "valor_unitario": "",
        "valor_total": _decimal_string(arredondar(consolidado.valor_total)),
        "quantidade_realizada": _decimal_string(consolidado.quantidade_realizada),
        "percentual_realizado": _decimal_string(consolidado.percentual_realizado),
        "valor_executado": _decimal_string(arredondar(consolidado.valor_executado)),
        "custo_unitario_realizado": "",
        "saldo": _decimal_string(arredondar(consolidado.valor_total - consolidado.valor_executado)),
        "status_execucao": consolidado.status_execucao,
        "semaforo": consolidado.semaforo or "",
    }


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
