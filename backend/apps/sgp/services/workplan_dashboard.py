"""Consultas e indicadores do painel de acompanhamento do Plano de Trabalho."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.models import WorkPlanAcao


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
PERCENTAGE_QUANTUM = Decimal("0.01")


def dashboard_actions() -> QuerySet[WorkPlanAcao]:
    """Retorna Ações com a quantidade concluída calculada em uma única consulta."""
    return WorkPlanAcao.objects.select_related("meta").annotate(
        _quantidade_realizada=Count(
            "atividades",
            filter=Q(atividades__status="concluido", atividades__ativo=True),
            distinct=True,
        )
    )


def dashboard_actions_for_user(user) -> QuerySet[WorkPlanAcao]:
    """Aplica a política de visibilidade do painel em um único ponto.

    Ações sem atividades ficam restritas a UGP e Super Admin. Alterações futuras
    nessa política devem ser feitas nesta função.
    """
    queryset = dashboard_actions()

    if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
        return queryset

    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        if not states:
            return queryset.none()
        return queryset.filter(
            atividades__municipio__state__sigla__in=states,
            atividades__ativo=True,
        ).distinct()

    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        if not territories.exists():
            return queryset.none()
        return queryset.filter(
            atividades__municipio__territory__in=territories,
            atividades__ativo=True,
        ).distinct()

    raise PermissionDenied("Você não tem acesso ao painel do Plano de Trabalho.")


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


def enrich_dashboard_action(action: WorkPlanAcao, today: date | None = None) -> WorkPlanAcao:
    """Anexa os indicadores calculados exigidos pelo painel à Ação informada."""
    today = today or date.today()
    quantidade_planejada = Decimal(action.quantidade_planejada or ZERO)
    quantidade_realizada = Decimal(getattr(action, "_quantidade_realizada", ZERO))

    percentual_realizado = (
        ZERO
        if quantidade_planejada <= ZERO
        else (quantidade_realizada / quantidade_planejada) * ONE_HUNDRED
    )
    data_inicio = action.data_inicio or action.meta.data_inicio
    data_fim = action.data_fim or action.meta.data_fim
    progresso_esperado = _expected_progress(data_inicio, data_fim, today)

    action.dashboard_quantidade_realizada = quantidade_realizada
    action.dashboard_percentual_realizado = _round_percentage(percentual_realizado)
    action.dashboard_progresso_esperado = _round_percentage(progresso_esperado)
    action.dashboard_semaforo = _semaphore(percentual_realizado, progresso_esperado)
    action.dashboard_status_execucao = _execution_status(
        quantidade_planejada, quantidade_realizada, data_fim, today
    )
    return action


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
    if quantidade_realizada >= quantidade_planejada:
        return "concluida"
    if today > data_fim:
        return "em_atraso"
    return "no_prazo"


def _round_percentage(value: Decimal) -> Decimal:
    return value.quantize(PERCENTAGE_QUANTUM, rounding=ROUND_HALF_UP)
