"""
Ordem de lock fixa em todo o módulo — `DemandIndividualLimit` primeiro
(`select_for_update` aqui), `BudgetAllocation` depois (travada dentro de
`apps.sgp.services.budget`) — nunca inverter, ou duas chamadas concorrentes
podem deadlockar.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.audit_log import AuditLog
from apps.sgd.models import DemandIndividualLimit
from apps.sgd.services import notifications as notifications_service
from apps.sgp.services import budget as budget_service

ZERO = Decimal("0")

TRAVA_INDIVIDUAL = "individual"
TRAVA_TERRITORIAL = "territorial"

_ENTIDADE_LIMITE = "DemandIndividualLimit"


ACAO_SUGERIDA = {
    TRAVA_INDIVIDUAL: "solicitar_recurso_extra",
    TRAVA_TERRITORIAL: "acionar_articulador",
}

ORIENTACAO_INDIVIDUAL = "Use a opção 'Solicitar recurso extra'."


def orientacao_territorial(*, allocation, saldo: Decimal | None) -> str:
    """Sem alocação nenhuma, afirmar que o território esgotou seria falso — só
    orienta. Com alocação, "esgotado" puro quando o saldo zerou; com saldo
    ainda positivo (ou desconhecido, numa corrida detectada pelo motor), o
    que esgotou foi a cobertura deste valor."""
    if allocation is None:
        return "Acione o Articulador Estadual para alocar saldo ao território."
    if saldo is not None and saldo <= ZERO:
        return "Território esgotado nesta rubrica. Acione o Articulador Estadual."
    return "Território esgotado nesta rubrica para este valor. Acione o Articulador Estadual."


def com_orientacao(motivo: str | None, orientacao: str) -> str | None:
    if not motivo:
        return motivo
    return f"{motivo} {orientacao}"


@dataclass
class TravaCheck:
    disponivel: bool
    saldo: Decimal
    motivo_bloqueio: str | None = None
    acao_sugerida: str | None = None


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


def faixas_antes_e_depois(
    *, comprometido: Decimal, total: Decimal, delta: Decimal, limiares: "budget_service.LimiaresSemaforo",
) -> tuple[str, str]:
    return (
        budget_service.faixa_semaforo(budget_service.percentual_comprometido(comprometido, total), limiares),
        budget_service.faixa_semaforo(budget_service.percentual_comprometido(comprometido + delta, total), limiares),
    )


_SEM_SEMAFORO = {"semaforo_atual": None, "semaforo_apos": None}


def _semaforos(*, comprometido: Decimal, total: Decimal, valor: Decimal, limiares) -> dict:
    atual, apos = faixas_antes_e_depois(comprometido=comprometido, total=total, delta=valor, limiares=limiares)
    return {"semaforo_atual": atual, "semaforo_apos": apos}


def _semaforos_individual(*, solicitante, rubrica, valor: Decimal, limiares) -> dict:
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    if limite is None:
        return dict(_SEM_SEMAFORO)
    return _semaforos(
        comprometido=limite.valor_comprometido, total=limite.valor_limite, valor=valor, limiares=limiares,
    )


def _semaforos_allocation(allocation, *, valor: Decimal, limiares) -> dict:
    if allocation is None:
        return dict(_SEM_SEMAFORO)
    return _semaforos(
        comprometido=allocation.valor_comprometido, total=allocation.valor_alocado, valor=valor, limiares=limiares,
    )


def payload_saldo_consulta(check: "DuasTravasCheck", *, solicitante, rubrica, valor: Decimal) -> dict:
    limiares = budget_service.limiares_semaforo()
    return {
        "individual": {
            "disponivel": check.individual.disponivel,
            "saldo": check.individual.saldo,
            "motivo_bloqueio": check.individual.motivo_bloqueio,
            "acao_sugerida": check.individual.acao_sugerida,
            **_semaforos_individual(solicitante=solicitante, rubrica=rubrica, valor=valor, limiares=limiares),
        },
        "territorial": {
            "disponivel": check.territorial.disponivel,
            "saldo": check.territorial.saldo,
            "motivo_bloqueio": check.territorial.motivo_bloqueio,
            "acao_sugerida": None if check.territorial.disponivel else ACAO_SUGERIDA[TRAVA_TERRITORIAL],
            **_semaforos_allocation(check.territorial.allocation, valor=valor, limiares=limiares),
        },
        "disponivel": check.disponivel,
        "trava_bloqueada": check.trava_bloqueada,
    }


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
    antes, depois = faixas_antes_e_depois(
        comprometido=comprometido_antes, total=limite, delta=comprometido_depois - comprometido_antes,
        limiares=budget_service.limiares_semaforo(),
    )
    if _ORDEM_SEMAFORO[depois] > _ORDEM_SEMAFORO[antes]:
        notifications_service.notificar_mudanca_semaforo(
            usuarios=usuarios, demand=demand, rubrica_nome=rubrica_nome, trava=trava, semaforo=depois,
        )


def _checar_individual(*, solicitante, rubrica, valor: Decimal) -> TravaCheck:
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    if limite is None:
        return TravaCheck(
            disponivel=False, saldo=ZERO,
            motivo_bloqueio=com_orientacao(
                f"Nenhum limite individual configurado para você nesta rubrica: "
                f"R$ 0.00 disponível, R$ {valor} solicitado.",
                ORIENTACAO_INDIVIDUAL,
            ),
            acao_sugerida=ACAO_SUGERIDA[TRAVA_INDIVIDUAL],
        )
    saldo = limite.saldo_disponivel
    if saldo <= ZERO:
        return TravaCheck(
            disponivel=False, saldo=saldo,
            motivo_bloqueio=com_orientacao(
                f"Limite individual esgotado para esta rubrica: R$ {saldo} disponível, "
                f"R$ {valor} solicitado.",
                ORIENTACAO_INDIVIDUAL,
            ),
            acao_sugerida=ACAO_SUGERIDA[TRAVA_INDIVIDUAL],
        )
    if valor > saldo:
        return TravaCheck(
            disponivel=False, saldo=saldo,
            motivo_bloqueio=com_orientacao(
                f"Limite individual insuficiente: R$ {saldo} disponível, R$ {valor} solicitado.",
                ORIENTACAO_INDIVIDUAL,
            ),
            acao_sugerida=ACAO_SUGERIDA[TRAVA_INDIVIDUAL],
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
    if not territorial.disponivel:
        territorial = replace(
            territorial, motivo_bloqueio=com_orientacao(
                territorial.motivo_bloqueio,
                orientacao_territorial(allocation=territorial.allocation, saldo=territorial.saldo),
            ),
        )
    return DuasTravasCheck(individual=individual, territorial=territorial)


def _ja_registrado(*, acao: str, entidade_id: str) -> bool:
    return AuditLog.objects.filter(entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao=acao).exists()


def reserva_ativa(demand_request) -> bool:
    """Estado atual da reserva desta solicitação — não "já reservou alguma
    vez", mas "está reservada agora". Distingue o ciclo reserva → liberação →
    nova reserva (edição em Devolvida, resubmissão) olhando só o último
    evento, não a existência histórica de um tipo de evento."""
    ultimo = AuditLog.objects.filter(
        entidade=_ENTIDADE_LIMITE, entidade_id=str(demand_request.pk), acao__in=["reserva", "liberacao"],
    ).order_by("-timestamp", "-id").values_list("acao", flat=True).first()
    return ultimo == "reserva"


def _registrar_movimento_individual(
    *, acao: str, entidade_id: str, usuario, valores_anteriores: dict | None = None, valores_novos: dict | None = None,
) -> None:
    AuditLog.objects.create(
        user=usuario, acao=acao, modulo="sgd", entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id,
        valores_anteriores=valores_anteriores or {}, valores_novos=valores_novos or {},
    )


@transaction.atomic
def reservar_duas_travas(*, demand_request, usuario) -> None:
    """Idempotente por `demand_request.pk`."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor = demand_request.valor_estimado
    meta = demand_request.meta

    entidade_id = str(demand_request.pk)
    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    comprometido_individual_antes = limite.valor_comprometido
    if not reserva_ativa(demand_request):
        # Reconfere o saldo com a linha já travada (select_for_update acima)
        # — sem isso, duas reservas concorrentes que passaram no
        # verificar_duas_travas (antes do lock) comprometeriam o limite além
        # do valor_limite.
        if valor > limite.saldo_disponivel:
            raise DRFValidationError({
                "detail": com_orientacao(
                    f"Limite individual insuficiente: R$ {limite.saldo_disponivel} disponível, "
                    f"R$ {valor} solicitado.",
                    ORIENTACAO_INDIVIDUAL,
                )
            })
        limite.valor_comprometido += valor
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="reserva", entidade_id=entidade_id, usuario=usuario,
            valores_novos={"limite_id": limite.pk, "valor": str(valor)},
        )
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
        raise DRFValidationError({
            "detail": com_orientacao(
                "Nenhuma alocação orçamentária territorial encontrada.",
                orientacao_territorial(allocation=None, saldo=None),
            )
        })
    comprometido_territorial_antes = check.allocation.valor_comprometido
    try:
        budget_service.reservar(
            allocation=check.allocation, valor=valor, demanda_id=str(demand_request.pk), usuario=usuario,
            justificativa=f"Reserva SGD — solicitação #{demand_request.pk}.",
        )
    except budget_service.SaldoInsuficienteError as exc:
        raise DRFValidationError({
            "detail": com_orientacao(str(exc), orientacao_territorial(allocation=check.allocation, saldo=None))
        }) from exc
    except ValueError as exc:
        raise DRFValidationError({"detail": str(exc)}) from exc
    check.allocation.refresh_from_db(fields=["valor_comprometido"])
    _notificar_se_piorou(
        usuarios=_destinatarios_saldo_territorial(nivel=nivel, estado_sigla=estado_sigla, territorio=territorio),
        demand=demand_request.demanda, rubrica_nome=rubrica.nome, trava=TRAVA_TERRITORIAL,
        comprometido_antes=comprometido_territorial_antes,
        comprometido_depois=check.allocation.valor_comprometido, limite=check.allocation.valor_alocado,
    )


def _valor_reservado_individual(entidade_id: str, *, fallback: Decimal) -> Decimal:
    """Última reserva/ajuste aplicado para esta entidade — nunca um campo
    congelado do model. Reaplicar `ajustar_duas_travas` com o mesmo
    `novo_valor` (retry) dá diferença zero por construção, sem precisar de
    uma guarda de "já processei esse evento"."""
    ultimo = AuditLog.objects.filter(
        entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id, acao__in=["reserva", "ajuste"],
    ).order_by("-timestamp", "-id").first()
    if ultimo is None:
        return fallback
    valor = (ultimo.valores_novos or {}).get("valor")
    return Decimal(valor) if valor is not None else fallback


@transaction.atomic
def ajustar_duas_travas(
    *, demand_request, novo_valor: Decimal, usuario, ignorar_limite_individual: bool = False,
) -> None:
    """`ignorar_limite_individual=True` autoriza um excedente pontual (RF16) sem
    alterar `valor_limite` — usada só pelo fluxo de remanejamento emergencial da UGP.

    Reutilizável mais de uma vez para a mesma solicitação (autorização com
    valor ajustado, depois edição em Devolvida, depois nova autorização
    etc.) — cada chamada reconsulta o valor efetivamente reservado agora,
    nunca um total acumulado só em memória."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    valor_anterior = _valor_reservado_individual(entidade_id, fallback=demand_request.valor_estimado)
    diferenca = novo_valor - valor_anterior
    comprometido_individual_antes = limite.valor_comprometido
    if diferenca != ZERO:
        if not ignorar_limite_individual and diferenca > ZERO and diferenca > limite.saldo_disponivel:
            raise DRFValidationError({
                "detail": com_orientacao(
                    f"Limite individual insuficiente para o ajuste: R$ {limite.saldo_disponivel} "
                    f"disponível, R$ {diferenca} a mais solicitado.",
                    ORIENTACAO_INDIVIDUAL,
                )
            })
        limite.valor_comprometido += diferenca
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="ajuste", entidade_id=entidade_id, usuario=usuario,
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

    try:
        budget_service.ajustar_reserva(
            demanda_id=entidade_id, novo_valor=novo_valor, usuario=usuario,
            justificativa=f"Ajuste SGD — solicitação #{demand_request.pk}.",
        )
    except budget_service.SaldoInsuficienteError as exc:
        raise DRFValidationError({
            "detail": com_orientacao(str(exc), orientacao_territorial(allocation=allocation_antes, saldo=None))
        }) from exc
    except (budget_service.DemandaInvalidaError, ValueError) as exc:
        raise DRFValidationError({"detail": str(exc)}) from exc

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
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().filter(
        solicitante=solicitante, rubrica=rubrica,
    ).first()
    # Só libera se há reserva ativa agora — cancelar um Rascunho (nunca
    # reservado) ou liberar duas vezes seguidas não pode decrementar o
    # comprometido de novo. E libera o valor efetivamente reservado agora
    # (último reserva/ajuste), não `valor_estimado` — que fica congelado no
    # valor original mesmo depois de um ajuste na autorização ou numa edição.
    if limite is not None and reserva_ativa(demand_request):
        valor = _valor_reservado_individual(entidade_id, fallback=demand_request.valor_estimado)
        limite.valor_comprometido -= valor
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="liberacao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={"limite_id": limite.pk, "valor": str(valor)},
        )

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
    if not _ja_registrado(acao="execucao", entidade_id=entidade_id):
        limite.valor_comprometido -= valor_reservado
        limite.valor_executado += valor_pago
        limite.save(update_fields=["valor_comprometido", "valor_executado"])
        _registrar_movimento_individual(
            acao="execucao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={"valor_pago": str(valor_pago), "diferenca_liberada": str(diferenca)},
        )

    try:
        budget_service.executar(demanda_id=str(demand_request.pk), usuario=usuario, valor_executado=valor_pago)
    except (budget_service.DemandaInvalidaError, ValueError) as exc:
        raise DRFValidationError({"detail": str(exc)}) from exc


@transaction.atomic
def autorizar_excedente(*, demand_request, origem_allocation, valor_excedente: Decimal,
                         justificativa: str, usuario) -> None:
    if not justificativa:
        raise DRFValidationError({"justificativa": "Obrigatória para autorizar excedente."})
    if origem_allocation.nivel not in (budget_service.Nivel.ESTADUAL, budget_service.Nivel.NACIONAL):
        raise DRFValidationError({
            "origem_allocation": "Remanejamento emergencial (RF16) só pode vir de saldo estadual ou nacional."
        })

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

    # Remanejamento é pontual: só move o pool territorial de origem pro destino
    # e libera esta solicitação específica via `ignorar_limite_individual` (em
    # `ajustar_duas_travas`) — não eleva `valor_limite`, ou o solicitante
    # ganharia teto maior permanentemente por um excedente de uma única vez.
    AuditLog.objects.create(
        user=usuario, acao="remanejamento_emergencial", modulo="sgd", entidade=_ENTIDADE_LIMITE,
        entidade_id=str(demand_request.pk),
        valores_novos={"valor_excedente": str(valor_excedente), "justificativa": justificativa},
    )
