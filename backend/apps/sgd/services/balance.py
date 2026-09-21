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
from apps.sgd.services import notifications as notifications_service
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


_ORDEM_SEMAFORO = {"verde": 0, "amarelo": 1, "vermelho": 2}


def _destinatarios_saldo_territorial(*, nivel, estado_sigla, territorio):
    if nivel == budget_service.Nivel.NACIONAL:
        return list(notifications_service.usuarios_por_perfil("ugp"))
    if nivel == budget_service.Nivel.ESTADUAL:
        return list(notifications_service.usuarios_articuladores_do_estado(estado_sigla))
    siglas = (territorio.estados if territorio else []) or []
    vistos = set()
    destinatarios = []
    for sigla in siglas:
        for usuario in notifications_service.usuarios_articuladores_do_estado(sigla):
            if usuario.pk not in vistos:
                vistos.add(usuario.pk)
                destinatarios.append(usuario)
    return destinatarios


def _notificar_se_piorou(*, usuarios, demand, rubrica_nome, trava, comprometido_antes, comprometido_depois, limite) -> None:
    antes = semaforo_sgd(percentual_comprometido(comprometido_antes, limite))
    depois = semaforo_sgd(percentual_comprometido(comprometido_depois, limite))
    if _ORDEM_SEMAFORO[depois] > _ORDEM_SEMAFORO[antes]:
        notifications_service.notificar_mudanca_semaforo(
            usuarios=usuarios, demand=demand, rubrica_nome=rubrica_nome, trava=trava, semaforo=depois,
        )


def _checar_individual(*, solicitante, rubrica, valor: Decimal) -> TravaCheck:
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    if limite is None:
        return TravaCheck(
            disponivel=False, saldo=ZERO,
            motivo_bloqueio=(
                f"Nenhum limite individual configurado para você nesta rubrica. "
                f"R$ 0.00 disponível, R$ {valor} solicitado. Solicite ao Super Admin."
            ),
        )
    saldo = limite.saldo_disponivel
    if saldo <= ZERO:
        return TravaCheck(
            disponivel=False, saldo=saldo,
            motivo_bloqueio=(
                f"Limite individual esgotado para esta rubrica: R$ {saldo} disponível, "
                f"R$ {valor} solicitado."
            ),
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
    meta = demand_request.meta

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    comprometido_individual_antes = limite.valor_comprometido
    if _log_movimento_individual(
        acao="reserva", limite=limite, demand_request=demand_request, valor=valor, usuario=usuario,
    ):
        # Reconfere o saldo com a linha já travada (select_for_update acima)
        # — sem isso, duas reservas concorrentes que passaram no
        # verificar_duas_travas (antes do lock) comprometeriam o limite além
        # do valor_limite.
        if valor > limite.saldo_disponivel:
            raise DRFValidationError({
                "detail": (
                    f"Limite individual insuficiente: R$ {limite.saldo_disponivel} disponível, "
                    f"R$ {valor} solicitado."
                )
            })
        limite.valor_comprometido += valor
        limite.save(update_fields=["valor_comprometido"])
        _notificar_se_piorou(
            usuarios=[solicitante], demand=demand_request.demanda, rubrica_nome=rubrica.nome,
            trava=TRAVA_INDIVIDUAL, comprometido_antes=comprometido_individual_antes,
            comprometido_depois=limite.valor_comprometido, limite=limite.valor_limite,
        )

    nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
    check = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=rubrica.slug, nivel=nivel,
        estado_sigla=estado_sigla, territorio=territorio, valor=valor,
    )
    if check.allocation is None:
        raise DRFValidationError({"detail": "Nenhuma alocação orçamentária territorial encontrada."})
    comprometido_territorial_antes = check.allocation.valor_comprometido
    budget_service.reservar(
        allocation=check.allocation, valor=valor, demanda_id=str(demand_request.pk), usuario=usuario,
        justificativa=f"Reserva SGD — solicitação #{demand_request.pk}.",
    )
    check.allocation.refresh_from_db(fields=["valor_comprometido"])
    _notificar_se_piorou(
        usuarios=_destinatarios_saldo_territorial(nivel=nivel, estado_sigla=estado_sigla, territorio=territorio),
        demand=demand_request.demanda, rubrica_nome=rubrica.nome, trava=TRAVA_TERRITORIAL,
        comprometido_antes=comprometido_territorial_antes,
        comprometido_depois=check.allocation.valor_comprometido, limite=check.allocation.valor_alocado,
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
    comprometido_individual_antes = limite.valor_comprometido
    if not AuditLog.objects.filter(entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao="ajuste").exists():
        if diferenca > ZERO and diferenca > limite.saldo_disponivel:
            raise DRFValidationError({
                "detail": (
                    f"Limite individual insuficiente para o ajuste: R$ {limite.saldo_disponivel} "
                    f"disponível, R$ {diferenca} a mais solicitado."
                )
            })
        limite.valor_comprometido += diferenca
        limite.save(update_fields=["valor_comprometido"])
        AuditLog.objects.create(
            user=usuario, acao="ajuste", modulo="sgd", entidade=_ENTIDADE_LIMITE,
            entidade_id=entidade_id,
            valores_anteriores={"valor": str(valor_anterior)},
            valores_novos={"valor": str(novo_valor)},
        )
        _notificar_se_piorou(
            usuarios=[solicitante], demand=demand_request.demanda, rubrica_nome=rubrica.nome,
            trava=TRAVA_INDIVIDUAL, comprometido_antes=comprometido_individual_antes,
            comprometido_depois=limite.valor_comprometido, limite=limite.valor_limite,
        )

    reserva_allocation_id = budget_service.BudgetTransaction.objects.filter(
        demanda_id=entidade_id, tipo=budget_service.BudgetTransaction.Tipo.RESERVA,
    ).values_list("allocation_id", flat=True).first()
    allocation_antes = (
        budget_service.BudgetAllocation.objects.get(pk=reserva_allocation_id) if reserva_allocation_id else None
    )
    comprometido_territorial_antes = allocation_antes.valor_comprometido if allocation_antes else ZERO

    budget_service.ajustar_reserva(
        demanda_id=entidade_id, novo_valor=novo_valor, usuario=usuario,
        justificativa=f"Ajuste SGD — solicitação #{demand_request.pk}.",
    )

    if allocation_antes is not None:
        allocation_antes.refresh_from_db(fields=["valor_comprometido", "valor_alocado"])
        nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
        _notificar_se_piorou(
            usuarios=_destinatarios_saldo_territorial(nivel=nivel, estado_sigla=estado_sigla, territorio=territorio),
            demand=demand_request.demanda, rubrica_nome=rubrica.nome, trava=TRAVA_TERRITORIAL,
            comprometido_antes=comprometido_territorial_antes,
            comprometido_depois=allocation_antes.valor_comprometido, limite=allocation_antes.valor_alocado,
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
    meta = demand_request.meta

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
