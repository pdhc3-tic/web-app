"""Consultas e indicadores do painel de acompanhamento do Plano de Trabalho."""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import QuerySet

from apps.sgp.constants import STATUS_CONCLUIDA
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta
from apps.sgp.models.workplan import CEM, arredondar, percentual, status_da_meta, status_execucao
from apps.sgp.services.apuracao import (
    FiltroAtividades,
    expressao_quantidade_realizada,
    filtro_de_atividades,
)
from apps.sgp.services.budget import LimiaresSemaforo, faixa_semaforo, limiares_semaforo
from apps.sgp.services.workplan_access import filter_workplan_actions_for_user


ZERO = Decimal("0")


def dashboard_actions(filtro: FiltroAtividades | None = None) -> QuerySet[WorkPlanAcao]:
    """Ações com a quantidade realizada apurada só sobre as Atividades que passam
    no filtro, numa única consulta. O valor executado é o da Ação inteira."""
    return WorkPlanAcao.objects.select_related("meta", "submeta", "indicador").annotate(
        _quantidade_realizada=expressao_quantidade_realizada(filtro),
    )


def dashboard_actions_for_user(user) -> QuerySet[WorkPlanAcao]:
    """Aplica a política de visibilidade do painel em um único ponto.

    Ações sem atividades só aparecem para quem lê o Plano de Trabalho inteiro
    (UGP, Super Admin e FGD). Alterações futuras nessa política devem ser
    feitas nesta função.
    """
    return filter_workplan_actions_for_user(dashboard_actions(filtro_de_atividades(user)), user)


def apply_dashboard_filters(
    queryset: QuerySet[WorkPlanAcao], *, meta_id: int | None = None,
    territorio_id: int | None = None,
) -> QuerySet[WorkPlanAcao]:
    """Aplica os filtros persistidos do painel antes do cálculo dos indicadores."""
    if meta_id is not None:
        queryset = queryset.filter(meta_id=meta_id)
    if territorio_id is not None:
        queryset = queryset.filter(
            atividades__municipio__territory_id=territorio_id,
            atividades__ativo=True,
        ).distinct()
    return queryset


def enrich_dashboard_action(
    action: WorkPlanAcao,
    today: date | None = None,
    limiares: LimiaresSemaforo | None = None,
) -> WorkPlanAcao:
    """Anexa os indicadores calculados exigidos pelo painel à Ação informada.

    Quem enriquece várias Ações deve ler `limiares_semaforo()` uma vez e
    repassar."""
    today = today or date.today()
    limiares = limiares or limiares_semaforo()
    quantidade_planejada = Decimal(action.quantidade_planejada or ZERO)
    quantidade_realizada = Decimal(getattr(action, "_quantidade_realizada", ZERO))
    valor_total = Decimal(action.valor_total or ZERO)
    valor_executado = Decimal(action.valor_executado or ZERO)

    percentual_realizado = percentual(quantidade_realizada, quantidade_planejada)
    progresso_esperado = _expected_progress(action.data_inicio, action.data_fim, today)
    percentual_financeiro = percentual(valor_executado, valor_total)

    action.dashboard_quantidade_realizada = quantidade_realizada
    action.dashboard_percentual_realizado = arredondar(percentual_realizado)
    action.dashboard_progresso_esperado = arredondar(progresso_esperado)
    action.dashboard_semaforo = _semaphore(percentual_realizado, progresso_esperado)
    action.dashboard_status_execucao = status_execucao(
        quantidade_realizada >= quantidade_planejada, action.data_fim, today
    )
    action.dashboard_valor_executado = valor_executado
    action.dashboard_percentual_financeiro = arredondar(percentual_financeiro)
    action.dashboard_semaforo_financeiro = _semaforo_financeiro(
        percentual_financeiro, valor_total, limiares
    )
    return action


@dataclass(frozen=True)
class NodeSummary:
    """Consolidado de um nó da árvore do PT (Submeta ou Meta) a partir das
    Ações já enriquecidas por `enrich_dashboard_action`."""

    quantidade_planejada: Decimal
    quantidade_realizada: Decimal
    percentual_realizado: Decimal
    progresso_esperado: Decimal
    semaforo: str | None
    status_execucao: str
    valor_total: Decimal
    valor_executado: Decimal
    percentual_financeiro: Decimal
    semaforo_financeiro: str | None


def summarize_node(
    acoes: Iterable[WorkPlanAcao],
    node: WorkPlanMeta | WorkPlanSubmeta,
    today: date,
    limiares: LimiaresSemaforo,
) -> NodeSummary:
    """O período do progresso esperado é o do `node` e o status sai das Ações.
    Sem planejado, não há percentual para o semáforo, que fica nulo."""
    acoes = list(acoes)
    planejado = sum((Decimal(a.quantidade_planejada) for a in acoes), ZERO)
    realizado = sum((a.dashboard_quantidade_realizada for a in acoes), ZERO)
    valor_total = sum((Decimal(a.valor_total) for a in acoes), ZERO)
    valor_executado = sum((a.dashboard_valor_executado for a in acoes), ZERO)

    percentual_realizado = percentual(realizado, planejado)
    progresso_esperado = _expected_progress(node.data_inicio, node.data_fim, today)
    percentual_financeiro = percentual(valor_executado, valor_total)
    concluido = bool(acoes) and all(
        a.dashboard_status_execucao == STATUS_CONCLUIDA for a in acoes
    )
    return NodeSummary(
        quantidade_planejada=planejado,
        quantidade_realizada=realizado,
        percentual_realizado=arredondar(percentual_realizado),
        progresso_esperado=arredondar(progresso_esperado),
        semaforo=_semaphore(percentual_realizado, progresso_esperado) if planejado > ZERO else None,
        status_execucao=status_execucao(concluido, node.data_fim, today),
        valor_total=valor_total,
        valor_executado=valor_executado,
        percentual_financeiro=arredondar(percentual_financeiro),
        semaforo_financeiro=_semaforo_financeiro(percentual_financeiro, valor_total, limiares),
    )


def summarize_meta(
    acoes: Iterable[WorkPlanAcao],
    meta: WorkPlanMeta,
    consolidados_das_submetas: list[NodeSummary],
    submetas_sem_acoes: int,
    today: date,
    limiares: LimiaresSemaforo,
) -> NodeSummary:
    """Consolidado da Meta, com o status calculado com base nas Submetas (SGP
    §5.2), pela mesma regra do model: as Submetas ainda sem Ações também
    contam, como não concluídas."""
    concluidas = [c.status_execucao == STATUS_CONCLUIDA for c in consolidados_das_submetas]
    status = status_da_meta(concluidas + [False] * submetas_sem_acoes, meta.data_fim, today)
    return replace(summarize_node(acoes, meta, today, limiares), status_execucao=status)


def submetas_sem_acoes_por_meta(meta_ids) -> Counter:
    return Counter(
        WorkPlanSubmeta.objects.filter(meta_id__in=meta_ids, acoes__isnull=True)
        .order_by()
        .values_list("meta_id", flat=True)
    )


def dashboard_tree(
    acoes: Iterable[WorkPlanAcao],
    limiares: LimiaresSemaforo,
    today: date | None = None,
) -> list[dict]:
    """Agrupa Ações já enriquecidas, na ordem do model (Meta e número), em
    Meta → Submeta, com o consolidado de cada nó calculado sobre as Ações
    recebidas (o filtro de status do painel, se aplicado, vale também para os
    consolidados)."""
    today = today or date.today()
    metas: dict[int, dict] = {}
    for acao in acoes:
        grupo = metas.setdefault(acao.meta_id, {
            "meta": acao.meta,
            "resumo": {"total_acoes": 0, "verde": 0, "amarelo": 0, "vermelho": 0},
            "acoes": [],
            "submetas": {},
        })
        grupo["resumo"]["total_acoes"] += 1
        grupo["resumo"][acao.dashboard_semaforo] += 1
        grupo["acoes"].append(acao)
        grupo["submetas"].setdefault(acao.submeta_id, (acao.submeta, []))[1].append(acao)

    vazias = submetas_sem_acoes_por_meta(metas)
    arvore = []
    for grupo in metas.values():
        grupo["submetas"] = [
            {
                "submeta": submeta,
                "consolidado": summarize_node(acoes_da_submeta, submeta, today, limiares),
                "acoes": [a.pk for a in acoes_da_submeta],
            }
            for submeta, acoes_da_submeta in grupo["submetas"].values()
        ]
        grupo["consolidado"] = summarize_meta(
            grupo["acoes"], grupo["meta"], [no["consolidado"] for no in grupo["submetas"]],
            vazias[grupo["meta"].pk], today, limiares,
        )
        arvore.append(grupo)
    return arvore


def _expected_progress(data_inicio: date, data_fim: date, today: date) -> Decimal:
    """Calcula o percentual de tempo transcorrido, limitado ao intervalo informado."""
    if today <= data_inicio:
        return ZERO
    if today >= data_fim:
        return CEM

    total_days = (data_fim - data_inicio).days
    if total_days <= 0:
        return CEM
    return Decimal((today - data_inicio).days) / Decimal(total_days) * CEM


def _semaforo_financeiro(
    percentual_financeiro: Decimal, valor_total: Decimal, limiares: LimiaresSemaforo
) -> str | None:
    """Sem valor total não há percentual financeiro, e o semáforo fica nulo."""
    return faixa_semaforo(percentual_financeiro, limiares) if valor_total > ZERO else None


def _semaphore(percentual_realizado: Decimal, progresso_esperado: Decimal) -> str:
    if percentual_realizado >= progresso_esperado:
        return "verde"
    if percentual_realizado >= progresso_esperado * Decimal("0.5"):
        return "amarelo"
    return "vermelho"

