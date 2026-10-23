"""Porta do SGD para o motor de saldo do SGP.

É o único módulo do SGD que importa `apps.sgp.services.budget` e
`apps.sgp.models.budget`. O motor ainda localiza a alocação pela Meta; aqui ela
é resolvida a partir da atividade da demanda, e nenhuma assinatura do SGD a
recebe. Erros do motor saem daqui como exceções de domínio do SGD.

As operações recebem solicitante e rubrica mesmo quando o motor de hoje só usa
a solicitação: sem a Meta, é por eles que o pool vai ser localizado.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.core.utils import formatar_brl
from apps.sgd.exceptions import TRAVA_TERRITORIAL, RegraDeNegocio, SaldoInsuficiente
from apps.sgp.models.budget import BudgetAllocation, BudgetTransaction
from apps.sgp.services import budget as budget_service

ZERO = Decimal("0")

Nivel = budget_service.Nivel
SaldoCheck = budget_service.SaldoCheck
LimiaresSemaforo = budget_service.LimiaresSemaforo

resolver_nivel_do_usuario = budget_service.resolver_nivel_do_usuario
limiares_semaforo = budget_service.limiares_semaforo
faixa_semaforo = budget_service.faixa_semaforo
percentual_comprometido = budget_service.percentual_comprometido
painel_orcamento = budget_service.painel_orcamento
painel_orcamento_para_usuario = budget_service.painel_orcamento_para_usuario


@dataclass
class MovimentoPool:
    """Alocação movimentada e o comprometido antes do movimento, para o aviso de
    mudança de faixa do semáforo."""
    allocation: BudgetAllocation | None
    comprometido_antes: Decimal
    nivel: str | None
    estado_sigla: str | None
    territorio: object | None


def _meta_id(*, demand_request=None, activity=None) -> int:
    if demand_request is not None:
        activity = demand_request.demanda.activity
    if activity is None:
        raise RegraDeNegocio("Sem atividade vinculada, não há como localizar o pool territorial.")
    return activity.acao.meta_id


def saldo_do_pool(allocation: BudgetAllocation) -> Decimal:
    return allocation.valor_alocado - allocation.valor_comprometido - allocation.valor_executado


def com_orientacao(motivo: str | None, orientacao: str) -> str | None:
    if not motivo:
        return motivo
    return f"{motivo} {orientacao}"


def com_consumo_previo(motivo: str | None, consumo_previo: Decimal) -> str | None:
    """Sem isso o solicitante vê um disponível menor que o do painel de saldo
    e não sabe por quê."""
    if not motivo or consumo_previo <= ZERO:
        return motivo
    return (
        f"{motivo} Já descontados {formatar_brl(consumo_previo)} de outras solicitações "
        "desta demanda na mesma rubrica."
    )


def orientacao_territorial(*, allocation, saldo: Decimal | None) -> str:
    """Sem alocação nenhuma, afirmar que o território esgotou seria falso — só
    orienta. Com alocação, "esgotado" puro quando o saldo zerou; com saldo
    ainda positivo (ou desconhecido), o que esgotou foi a cobertura deste
    valor."""
    if allocation is None:
        return "Acione o Articulador Estadual para alocar saldo ao território."
    if saldo is not None and saldo <= ZERO:
        return "Território esgotado nesta rubrica. Acione o Articulador Estadual."
    return "Território esgotado nesta rubrica para este valor. Acione o Articulador Estadual."


def mensagem_territorial(*, allocation, disponivel: Decimal, solicitado: Decimal,
                         consumo_previo: Decimal = ZERO, ajuste: bool = False) -> str:
    valores = (
        f"{formatar_brl(disponivel)} disponível, {formatar_brl(solicitado)} "
        f"{'a mais solicitado' if ajuste else 'solicitado'}."
    )
    if allocation is None:
        motivo = f"Nenhuma alocação orçamentária territorial encontrada: {valores}"
    elif disponivel <= ZERO and consumo_previo <= ZERO:
        # Zerado só pelo consumo da própria demanda não é rubrica esgotada:
        # cai no "insuficiente".
        motivo = f"Saldo territorial zerado nesta rubrica: {valores}"
    elif ajuste:
        motivo = f"Saldo territorial insuficiente para o ajuste: {valores}"
    else:
        motivo = f"Saldo territorial insuficiente: {valores}"
    # A orientação olha o saldo real do pool: se ele só zerou por causa desta
    # demanda, o território não está esgotado.
    return com_orientacao(
        com_consumo_previo(motivo, consumo_previo),
        orientacao_territorial(allocation=allocation, saldo=disponivel + consumo_previo),
    )


def bloqueio_territorial(*, rubrica, allocation, disponivel: Decimal, solicitado: Decimal,
                         consumo_previo: Decimal = ZERO, ajuste: bool = False,
                         solicitacao_id: int | None = None) -> SaldoInsuficiente:
    return SaldoInsuficiente(
        trava=TRAVA_TERRITORIAL, rubrica=rubrica.slug, disponivel=disponivel, solicitado=solicitado,
        detail=mensagem_territorial(
            allocation=allocation, disponivel=disponivel, solicitado=solicitado,
            consumo_previo=consumo_previo, ajuste=ajuste,
        ),
        solicitacao_id=solicitacao_id,
    )


def consultar_pool(*, solicitante, rubrica, valor: Decimal, demand_request=None, activity=None,
                   consumo_previo: Decimal = ZERO) -> SaldoCheck:
    """Somente leitura. `activity` atende quem ainda não tem solicitação: a
    consulta de saldo do formulário e o recurso extra sem demanda.
    `consumo_previo` é o que a mesma operação ainda vai reservar nesta
    alocação antes de `valor`."""
    nivel, estado_sigla, territorio = resolver_nivel_do_usuario(solicitante)
    check = budget_service.saldo_para_consulta(
        meta_id=_meta_id(demand_request=demand_request, activity=activity), rubrica_slug=rubrica.slug,
        nivel=nivel, estado_sigla=estado_sigla, territorio=territorio, valor=valor,
        consumo_previo=consumo_previo,
    )
    if check.disponivel:
        return check
    return SaldoCheck(
        disponivel=False, saldo=check.saldo, allocation=check.allocation,
        motivo_bloqueio=mensagem_territorial(
            allocation=check.allocation, disponivel=check.saldo, solicitado=valor, consumo_previo=consumo_previo,
        ),
    )


def localizar_pool(*, solicitante, rubrica, demand_request=None, activity=None) -> BudgetAllocation:
    """Alocação territorial do solicitante, para quem decide por ele (a UGP no
    recurso extra). A falta de nível do solicitante não é falta de acesso de
    quem decide: vira 400, não 403."""
    try:
        check = consultar_pool(
            solicitante=solicitante, rubrica=rubrica, valor=ZERO,
            demand_request=demand_request, activity=activity,
        )
    except budget_service.PermissionDenied as exc:
        raise RegraDeNegocio(f"Não há como conferir o pool territorial do solicitante. {exc.detail}") from exc
    if check.allocation is None:
        raise RegraDeNegocio("Nenhuma alocação territorial encontrada para o solicitante nesta rubrica.")
    return check.allocation


def reservar_pool(*, solicitante, rubrica, valor: Decimal, demand_request, usuario) -> MovimentoPool:
    """Idempotente por `demand_request.pk` (o motor confere a reserva já feita
    depois de travar a alocação)."""
    nivel, estado_sigla, territorio = resolver_nivel_do_usuario(solicitante)
    check = budget_service.saldo_para_consulta(
        meta_id=_meta_id(demand_request=demand_request), rubrica_slug=rubrica.slug, nivel=nivel,
        estado_sigla=estado_sigla, territorio=territorio, valor=valor,
    )
    allocation = check.allocation
    if allocation is None:
        raise bloqueio_territorial(
            rubrica=rubrica, allocation=None, disponivel=ZERO, solicitado=valor, solicitacao_id=demand_request.pk,
        )
    comprometido_antes = allocation.valor_comprometido
    try:
        budget_service.reservar(
            allocation=allocation, valor=valor, demanda_id=str(demand_request.pk), usuario=usuario,
            justificativa=f"Reserva SGD — solicitação #{demand_request.pk}.",
        )
    except budget_service.SaldoInsuficienteError as exc:
        allocation.refresh_from_db()
        raise bloqueio_territorial(
            rubrica=rubrica, allocation=allocation, disponivel=saldo_do_pool(allocation), solicitado=valor,
            solicitacao_id=demand_request.pk,
        ) from exc
    except ValueError as exc:
        raise RegraDeNegocio(str(exc)) from exc
    allocation.refresh_from_db(fields=["valor_comprometido"])
    return MovimentoPool(allocation, comprometido_antes, nivel, estado_sigla, territorio)


def pool_da_reserva(demand_request) -> BudgetAllocation | None:
    allocation_id = BudgetTransaction.objects.filter(
        demanda_id=str(demand_request.pk), tipo=BudgetTransaction.Tipo.RESERVA,
    ).values_list("allocation_id", flat=True).first()
    return BudgetAllocation.objects.get(pk=allocation_id) if allocation_id else None


def total_reservado(demanda_id: str) -> Decimal:
    """Reserva original mais os ajustes, como o motor executa e libera."""
    return budget_service._valor_total_reservado(demanda_id)


def ajustar_pool(*, solicitante, rubrica, valor: Decimal, demand_request, usuario) -> MovimentoPool:
    """`valor` é o novo total reservado para a solicitação, não o delta."""
    entidade_id = str(demand_request.pk)
    allocation = pool_da_reserva(demand_request)
    comprometido_antes = allocation.valor_comprometido if allocation else ZERO
    try:
        budget_service.ajustar_reserva(
            demanda_id=entidade_id, novo_valor=valor, usuario=usuario,
            justificativa=f"Ajuste SGD — solicitação #{demand_request.pk}.",
        )
    except budget_service.SaldoInsuficienteError as exc:
        allocation.refresh_from_db()
        raise bloqueio_territorial(
            rubrica=rubrica, allocation=allocation, disponivel=saldo_do_pool(allocation),
            solicitado=valor - total_reservado(entidade_id), ajuste=True, solicitacao_id=demand_request.pk,
        ) from exc
    except (budget_service.DemandaInvalidaError, ValueError) as exc:
        raise RegraDeNegocio(str(exc)) from exc
    nivel, estado_sigla, territorio = resolver_nivel_do_usuario(solicitante) if allocation else (None, None, None)
    if allocation is not None:
        allocation.refresh_from_db(fields=["valor_comprometido", "valor_alocado"])
    return MovimentoPool(allocation, comprometido_antes, nivel, estado_sigla, territorio)


def liberar_pool(*, solicitante, rubrica, demand_request, usuario, motivo: str) -> None:
    """Sem `valor`: o motor devolve o que a própria reserva registrou (reserva
    mais ajustes), que é o que tem de voltar ao pool."""
    try:
        budget_service.liberar(demanda_id=str(demand_request.pk), usuario=usuario, motivo=motivo)
    except budget_service.DemandaInvalidaError:
        # Nunca chegou a reservar (ex.: bloqueada antes da submissão) — nada a liberar.
        pass


def executar_pool(*, solicitante, rubrica, valor: Decimal, demand_request, usuario) -> None:
    """`valor` é o valor pago; a diferença para o reservado volta ao pool."""
    try:
        budget_service.executar(demanda_id=str(demand_request.pk), usuario=usuario, valor_executado=valor)
    except (budget_service.DemandaInvalidaError, ValueError) as exc:
        raise RegraDeNegocio(str(exc)) from exc


def _travar_em_ordem_de_pk(queryset) -> None:
    list(queryset.select_for_update().order_by("pk").values_list("pk", flat=True))


def travar_pools_das_reservas(solicitacoes) -> None:
    """Trava, em ordem de pk, as alocações em que as solicitações têm reserva."""
    _travar_em_ordem_de_pk(BudgetAllocation.objects.filter(
        pk__in=BudgetTransaction.objects.filter(
            tipo=BudgetTransaction.Tipo.RESERVA, demanda_id__in=[str(s.pk) for s in solicitacoes],
        ).values("allocation_id"),
    ))


def travar_pools(pks) -> dict[int, BudgetAllocation]:
    """Relê as alocações travadas, em ordem crescente de pk, como `remanejar`.
    `of=("self",)`: estado e território vêm no join e o Postgres não aceita FOR
    UPDATE no lado anulável dele."""
    return {
        pk: BudgetAllocation.objects.select_for_update(of=("self",)).select_related("estado", "territorio").get(pk=pk)
        for pk in sorted(set(pks))
    }


def remanejar(*, origem: BudgetAllocation, destino: BudgetAllocation, valor: Decimal, usuario,
              justificativa: str) -> None:
    """Confere o saldo da origem já travada para a recusa sair em reais. O motor
    trava de novo, na mesma transação e na mesma ordem, e repete a conferência."""
    # Origem e destino incompatíveis ficam com a recusa do próprio motor.
    compativeis = origem.meta_id == destino.meta_id and origem.rubrica_id == destino.rubrica_id
    if origem.pk != destino.pk and compativeis:
        disponivel = saldo_do_pool(travar_pools({origem.pk, destino.pk})[origem.pk])
        if valor > disponivel:
            raise RegraDeNegocio(
                f"Saldo insuficiente na origem: {formatar_brl(disponivel)} disponível, "
                f"{formatar_brl(valor)} solicitado.",
                campo="valor",
            )
    budget_service.remanejar(origem=origem, destino=destino, valor=valor, usuario=usuario, justificativa=justificativa)
