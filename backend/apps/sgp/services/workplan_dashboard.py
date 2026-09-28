"""Consultas e indicadores do painel de acompanhamento do Plano de Trabalho."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.db.models import QuerySet

from apps.sgp.models import WorkPlanAcao
from apps.sgp.services.apuracao import FiltroAtividades, expressao_quantidade_realizada
from apps.sgp.services.budget import LimiaresSemaforo, faixa_semaforo, limiares_semaforo
from apps.sgp.services.workplan_access import (
    activity_scope_for_user,
    filter_workplan_actions_for_user,
)


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
PERCENTAGE_QUANTUM = Decimal("0.01")


def filtro_de_escopo(user) -> FiltroAtividades | None:
    """Filtro de Atividades do escopo territorial do usuário, no formato que a
    apuração espera; None para quem tem visão global."""
    if activity_scope_for_user(user) is None:
        return None
    return lambda prefixo: activity_scope_for_user(user, prefix=prefixo)


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
    return filter_workplan_actions_for_user(dashboard_actions(filtro_de_escopo(user)), user)


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
    action.dashboard_percentual_realizado = _round_percentage(percentual_realizado)
    action.dashboard_progresso_esperado = _round_percentage(progresso_esperado)
    action.dashboard_semaforo = _semaphore(percentual_realizado, progresso_esperado)
    action.dashboard_status_execucao = _execution_status(
        quantidade_planejada, quantidade_realizada, action.data_fim, today
    )
    action.dashboard_valor_executado = valor_executado
    action.dashboard_percentual_financeiro = _round_percentage(percentual_financeiro)
    action.dashboard_semaforo_financeiro = faixa_semaforo(percentual_financeiro, limiares)
    return action


@dataclass(frozen=True)
class ConsolidadoNo:
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


def consolidar_no(
    acoes: Iterable[WorkPlanAcao],
    data_inicio: date,
    data_fim: date,
    today: date,
    limiares: LimiaresSemaforo,
) -> ConsolidadoNo:
    acoes = list(acoes)
    planejado = sum((Decimal(a.quantidade_planejada) for a in acoes), ZERO)
    realizado = sum((a.dashboard_quantidade_realizada for a in acoes), ZERO)
    valor_total = sum((Decimal(a.valor_total) for a in acoes), ZERO)
    valor_executado = sum((a.dashboard_valor_executado for a in acoes), ZERO)

    percentual_realizado = percentual(realizado, planejado)
    progresso_esperado = _expected_progress(data_inicio, data_fim, today)
    percentual_financeiro = percentual(valor_executado, valor_total)
    concluido = bool(acoes) and all(
        a.dashboard_status_execucao == "concluida" for a in acoes
    )
    return ConsolidadoNo(
        quantidade_planejada=planejado,
        quantidade_realizada=realizado,
        percentual_realizado=_round_percentage(percentual_realizado),
        progresso_esperado=_round_percentage(progresso_esperado),
        semaforo=_semaphore(percentual_realizado, progresso_esperado),
        status_execucao=_status(concluido, data_fim, today),
        valor_total=valor_total,
        valor_executado=valor_executado,
        percentual_financeiro=_round_percentage(percentual_financeiro),
        semaforo_financeiro=faixa_semaforo(percentual_financeiro, limiares),
    )


def arvore_do_painel(
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
        meta = grupo["meta"]
        grupo["consolidado"] = consolidar_no(
            grupo["acoes"], meta.data_inicio, meta.data_fim, today, limiares
        )
        grupo["submetas"] = [
            {
                "submeta": submeta,
                "consolidado": consolidar_no(
                    acoes_da_submeta, submeta.data_inicio, submeta.data_fim, today, limiares
                ),
                "acoes": [a.pk for a in acoes_da_submeta],
            }
            for submeta, acoes_da_submeta in sorted(
                grupo["submetas"].values(), key=lambda item: item[0].numero
            )
        ]
        arvore.append(grupo)
    return arvore


def percentual(parte: Decimal, total: Decimal) -> Decimal:
    """Percentual sem arredondar, para comparar com limiares; exibição passa por
    `percentual_arredondado`."""
    if total <= ZERO:
        return ZERO
    return (Decimal(parte) / total) * ONE_HUNDRED


def percentual_arredondado(parte: Decimal, total: Decimal) -> Decimal:
    return _round_percentage(percentual(parte, total))


def _expected_progress(data_inicio: date, data_fim: date, today: date) -> Decimal:
    """Calcula o percentual de tempo transcorrido, limitado ao intervalo da Ação."""
    if today <= data_inicio:
        return ZERO
    if today >= data_fim:
        return ONE_HUNDRED

    total_days = (data_fim - data_inicio).days
    if total_days <= 0:
        return ONE_HUNDRED
    return Decimal((today - data_inicio).days) / Decimal(total_days) * ONE_HUNDRED


def _semaphore(percentual_realizado: Decimal, progresso_esperado: Decimal) -> str:
    if percentual_realizado >= progresso_esperado:
        return "verde"
    if percentual_realizado >= progresso_esperado * Decimal("0.5"):
        return "amarelo"
    return "vermelho"


def _execution_status(
    quantidade_planejada: Decimal,
    quantidade_realizada: Decimal,
    data_fim: date,
    today: date,
) -> str:
    return _status(quantidade_realizada >= quantidade_planejada, data_fim, today)


def _status(concluido: bool, data_fim: date, today: date) -> str:
    if concluido:
        return "concluida"
    if today > data_fim:
        return "em_atraso"
    return "no_prazo"


def _round_percentage(value: Decimal) -> Decimal:
    return value.quantize(PERCENTAGE_QUANTUM, rounding=ROUND_HALF_UP)
