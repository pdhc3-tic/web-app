"""Consultas e indicadores do painel de acompanhamento do Plano de Trabalho."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import QuerySet

from apps.sgp.constants import STATUS_CONCLUIDA
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta
from apps.sgp.models.workplan import CEM, arredondar, chave_do_numero, percentual, status_execucao
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

    Ações sem atividades ficam restritas a UGP e Super Admin. Alterações futuras
    nessa política devem ser feitas nesta função.
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
    action.dashboard_semaforo_financeiro = faixa_semaforo(percentual_financeiro, limiares)
    return action


@dataclass(frozen=True)
class NodeSummary:
    """Consolidado de um nó da árvore do PT (Submeta ou Meta) a partir das
    Ações já enriquecidas por `enrich_dashboard_action`."""

    quantidade_planejada: Decimal
    quantidade_realizada: Decimal
    percentual_realizado: Decimal
    progresso_esperado: Decimal
    semaforo: str
    status_execucao: str
    valor_total: Decimal
    valor_executado: Decimal
    percentual_financeiro: Decimal
    semaforo_financeiro: str


def summarize_node(
    acoes: Iterable[WorkPlanAcao],
    node: WorkPlanMeta | WorkPlanSubmeta,
    today: date,
    limiares: LimiaresSemaforo,
) -> NodeSummary:
    """O período do progresso esperado é o do `node`."""
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
        semaforo=_semaphore(percentual_realizado, progresso_esperado),
        status_execucao=status_execucao(concluido, node.data_fim, today),
        valor_total=valor_total,
        valor_executado=valor_executado,
        percentual_financeiro=arredondar(percentual_financeiro),
        semaforo_financeiro=faixa_semaforo(percentual_financeiro, limiares),
    )


def dashboard_tree(
    acoes: Iterable[WorkPlanAcao],
    limiares: LimiaresSemaforo,
    today: date | None = None,
) -> list[dict]:
    """Agrupa Ações já enriquecidas em Meta → Submeta, com o consolidado de cada
    nó calculado sobre as Ações recebidas (o filtro de status do painel, se
    aplicado, vale também para os consolidados)."""
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

    arvore = []
    for grupo in metas.values():
        grupo["acoes"].sort(key=lambda acao: chave_do_numero(acao.numero))
        grupo["consolidado"] = summarize_node(grupo["acoes"], grupo["meta"], today, limiares)
        grupo["submetas"] = [
            {
                "submeta": submeta,
                "consolidado": summarize_node(acoes_da_submeta, submeta, today, limiares),
                "acoes": [
                    a.pk for a in sorted(acoes_da_submeta, key=lambda a: chave_do_numero(a.numero))
                ],
            }
            for submeta, acoes_da_submeta in sorted(
                grupo["submetas"].values(), key=lambda item: chave_do_numero(item[0].numero)
            )
        ]
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


def _semaphore(percentual_realizado: Decimal, progresso_esperado: Decimal) -> str:
    if percentual_realizado >= progresso_esperado:
        return "verde"
    if percentual_realizado >= progresso_esperado * Decimal("0.5"):
        return "amarelo"
    return "vermelho"

