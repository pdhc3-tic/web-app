"""
Ordem de lock fixa em todo o módulo — `DemandIndividualLimit` primeiro
(`select_for_update` aqui), `BudgetAllocation` depois (travada dentro de
`apps.sgp.services.budget`) — nunca inverter, ou duas chamadas concorrentes
podem deadlockar.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.audit_log import AuditLog
from apps.sgd.models import DemandIndividualLimit
from apps.sgp.services import budget as budget_service

ZERO = Decimal("0")

LIMIAR_AMARELO_SGD = Decimal("70")
LIMIAR_VERMELHO_SGD = Decimal("90")

TRAVA_INDIVIDUAL = "individual"
TRAVA_TERRITORIAL = "territorial"

_ENTIDADE_LIMITE = "DemandIndividualLimit"


@dataclass
class TravaCheck:
    disponivel: bool
    saldo: Decimal
    motivo_bloqueio: str | None = None


@dataclass
class DuasTravasCheck:
    individual: TravaCheck
    territorial: "budget_service.SaldoCheck"

    @property
    def disponivel(self) -> bool:
        return self.individual.disponivel and self.territorial.disponivel

    @property
    def trava_bloqueada(self) -> str | None:
        if not self.individual.disponivel:
            return TRAVA_INDIVIDUAL
        if not self.territorial.disponivel:
            return TRAVA_TERRITORIAL
        return None


def semaforo_sgd(percentual: Decimal) -> str:
    if percentual >= LIMIAR_VERMELHO_SGD:
        return "vermelho"
    if percentual >= LIMIAR_AMARELO_SGD:
        return "amarelo"
    return "verde"


def percentual_comprometido(comprometido: Decimal, limite: Decimal) -> Decimal:
    if limite <= ZERO:
        return ZERO
    return (comprometido / limite) * Decimal("100")


def _checar_individual(*, solicitante, rubrica, valor: Decimal) -> TravaCheck:
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    if limite is None:
        return TravaCheck(
            disponivel=False, saldo=ZERO,
            motivo_bloqueio=(
                "Nenhum limite individual configurado para você nesta rubrica. "
                "Solicite ao Super Admin."
            ),
        )
    saldo = limite.saldo_disponivel
    if saldo <= ZERO:
        return TravaCheck(
            disponivel=False, saldo=saldo,
            motivo_bloqueio="Limite individual esgotado para esta rubrica.",
        )
    if valor > saldo:
        return TravaCheck(
            disponivel=False, saldo=saldo,
            motivo_bloqueio=f"Limite individual insuficiente: R$ {saldo} disponível, R$ {valor} solicitado.",
        )
    return TravaCheck(disponivel=True, saldo=saldo, motivo_bloqueio=None)


def verificar_duas_travas(*, solicitante, rubrica, meta, valor: Decimal) -> DuasTravasCheck:
    """Somente leitura — não reserva nada. `meta`/`rubrica` já resolvidas."""
    individual = _checar_individual(solicitante=solicitante, rubrica=rubrica, valor=valor)

    nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
    territorial = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=rubrica.slug, nivel=nivel,
        estado_sigla=estado_sigla, territorio=territorio, valor=valor,
    )
    return DuasTravasCheck(individual=individual, territorial=territorial)


def _log_movimento_individual(*, acao: str, limite: DemandIndividualLimit, demand_request, valor: Decimal, usuario) -> bool:
    """Devolve False sem criar nada se este movimento já foi registrado —
    idempotência por `demand_request.pk` + `acao`."""
    entidade_id = str(demand_request.pk)
    if AuditLog.objects.filter(entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao=acao).exists():
        return False
    AuditLog.objects.create(
        user=usuario, acao=acao, modulo="sgd", entidade=_ENTIDADE_LIMITE,
        entidade_id=entidade_id,
        valores_novos={"limite_id": limite.pk, "valor": str(valor)},
    )
    return True


@transaction.atomic
def reservar_duas_travas(*, demand_request, usuario) -> None:
    """Idempotente por `demand_request.pk`."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor = demand_request.valor_estimado
    meta = demand_request.demanda.activity.acao.meta

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    if _log_movimento_individual(
        acao="reserva", limite=limite, demand_request=demand_request, valor=valor, usuario=usuario,
    ):
        limite.valor_comprometido += valor
        limite.save(update_fields=["valor_comprometido"])

    nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
    check = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=rubrica.slug, nivel=nivel,
        estado_sigla=estado_sigla, territorio=territorio, valor=valor,
    )
    if check.allocation is None:
        raise DRFValidationError({"detail": "Nenhuma alocação orçamentária territorial encontrada."})
    budget_service.reservar(
        allocation=check.allocation, valor=valor, demanda_id=str(demand_request.pk), usuario=usuario,
        justificativa=f"Reserva SGD — solicitação #{demand_request.pk}.",
    )


@transaction.atomic
def ajustar_duas_travas(*, demand_request, novo_valor: Decimal, usuario) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor_anterior = demand_request.valor_estimado
    diferenca = novo_valor - valor_anterior
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    if not AuditLog.objects.filter(entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao="ajuste").exists():
        limite.valor_comprometido += diferenca
        limite.save(update_fields=["valor_comprometido"])
        AuditLog.objects.create(
            user=usuario, acao="ajuste", modulo="sgd", entidade=_ENTIDADE_LIMITE,
            entidade_id=entidade_id,
            valores_anteriores={"valor": str(valor_anterior)},
            valores_novos={"valor": str(novo_valor)},
        )

    budget_service.ajustar_reserva(
        demanda_id=entidade_id, novo_valor=novo_valor, usuario=usuario,
        justificativa=f"Ajuste SGD — solicitação #{demand_request.pk}.",
    )


@transaction.atomic
def liberar_duas_travas(*, demand_request, usuario, motivo: str) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor = demand_request.valor_estimado
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().filter(
        solicitante=solicitante, rubrica=rubrica,
    ).first()
    if limite is not None and _log_movimento_individual(
        acao="liberacao", limite=limite, demand_request=demand_request, valor=valor, usuario=usuario,
    ):
        limite.valor_comprometido -= valor
        limite.save(update_fields=["valor_comprometido"])

    try:
        budget_service.liberar(demanda_id=str(demand_request.pk), usuario=usuario, motivo=motivo)
    except budget_service.DemandaInvalidaError:
        # Nunca chegou a reservar (ex.: bloqueada antes da submissão) — nada a liberar.
        pass


@transaction.atomic
def executar_duas_travas(*, demand_request, valor_pago: Decimal, usuario) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor_reservado = demand_request.valor_autorizado or demand_request.valor_estimado
    diferenca = valor_reservado - valor_pago
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    if not AuditLog.objects.filter(entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao="execucao").exists():
        limite.valor_comprometido -= valor_reservado
        limite.valor_executado += valor_pago
        limite.save(update_fields=["valor_comprometido", "valor_executado"])
        AuditLog.objects.create(
            user=usuario, acao="execucao", modulo="sgd", entidade=_ENTIDADE_LIMITE,
            entidade_id=entidade_id,
            valores_novos={"valor_pago": str(valor_pago), "diferenca_liberada": str(diferenca)},
        )

    budget_service.executar(demanda_id=str(demand_request.pk), usuario=usuario, valor_executado=valor_pago)


@transaction.atomic
def autorizar_excedente(*, demand_request, origem_allocation, valor_excedente: Decimal,
                         justificativa: str, usuario) -> None:
    if not justificativa:
        raise DRFValidationError({"justificativa": "Obrigatória para autorizar excedente."})

    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    meta = demand_request.demanda.activity.acao.meta

    nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
    destino_check = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=rubrica.slug, nivel=nivel,
        estado_sigla=estado_sigla, territorio=territorio, valor=ZERO,
    )
    if destino_check.allocation is None:
        raise DRFValidationError({"detail": "Nenhuma alocação territorial encontrada para remanejar."})

    budget_service.remanejar(
        origem=origem_allocation, destino=destino_check.allocation, valor=valor_excedente,
        usuario=usuario, justificativa=justificativa,
    )

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    limite.valor_limite += valor_excedente
    limite.save(update_fields=["valor_limite"])
    AuditLog.objects.create(
        user=usuario, acao="remanejamento_emergencial", modulo="sgd", entidade=_ENTIDADE_LIMITE,
        entidade_id=str(demand_request.pk),
        valores_novos={"valor_excedente": str(valor_excedente), "justificativa": justificativa},
    )
