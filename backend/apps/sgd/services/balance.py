"""
Ordem de lock fixa em todo o módulo — `DemandIndividualLimit` primeiro
(`select_for_update` aqui), `BudgetAllocation` depois (travada dentro do motor
do SGP, via `apps.sgd.services.orcamento`) — nunca inverter, ou duas chamadas
concorrentes podem deadlockar.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from django.db import transaction

from apps.core.models.audit_log import AuditLog
from apps.core.signals.audit import get_audit_context
from apps.core.utils import formatar_brl
from apps.sgd.exceptions import (
    ACAO_SUGERIDA,
    TRAVA_INDIVIDUAL,
    TRAVA_TERRITORIAL,
    JustificativaObrigatoria,
    RegraDeNegocio,
    SaldoInsuficiente,
)
from apps.sgd.models import DemandIndividualLimit, DemandRequest
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services import orcamento as orcamento_service
from apps.sgd.services.orcamento import com_consumo_previo, com_orientacao

ZERO = Decimal("0")

_ENTIDADE_LIMITE = "DemandIndividualLimit"

ORIENTACAO_INDIVIDUAL = "Use a opção 'Solicitar recurso extra'."


def _mensagem_individual(*, limite, saldo: Decimal, valor: Decimal, consumo_previo: Decimal = ZERO) -> str:
    if limite is None:
        motivo = (
            f"Nenhum limite individual configurado para você nesta rubrica: "
            f"{formatar_brl(ZERO)} disponível, {formatar_brl(valor)} solicitado."
        )
    elif saldo <= ZERO and consumo_previo <= ZERO:
        # Zerado pelas outras solicitações da própria demanda não é limite
        # esgotado: cai no "insuficiente", que mostra disponível e solicitado.
        motivo = (
            f"Limite individual esgotado para esta rubrica: {formatar_brl(saldo)} disponível, "
            f"{formatar_brl(valor)} solicitado."
        )
    else:
        motivo = com_consumo_previo(
            f"Limite individual insuficiente: {formatar_brl(saldo)} disponível, {formatar_brl(valor)} solicitado.",
            consumo_previo,
        )
    return com_orientacao(motivo, ORIENTACAO_INDIVIDUAL)


def _bloqueio_individual(*, rubrica, limite, saldo: Decimal, valor: Decimal,
                         solicitacao_id: int | None = None) -> SaldoInsuficiente:
    return SaldoInsuficiente(
        trava=TRAVA_INDIVIDUAL, rubrica=rubrica.slug, disponivel=saldo, solicitado=valor,
        detail=_mensagem_individual(limite=limite, saldo=saldo, valor=valor), solicitacao_id=solicitacao_id,
    )


@dataclass
class TravaCheck:
    disponivel: bool
    saldo: Decimal
    motivo_bloqueio: str | None = None
    acao_sugerida: str | None = None
    # Limite lido na checagem, reaproveitado no payload (evita 2ª query).
    limite: DemandIndividualLimit | None = None


@dataclass
class DuasTravasCheck:
    individual: TravaCheck
    territorial: "orcamento_service.SaldoCheck"
    rubrica: object
    valor: Decimal

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

    def bloqueio(self, *, solicitacao_id: int | None = None) -> SaldoInsuficiente | None:
        trava = self.trava_bloqueada
        if trava is None:
            return None
        check = self.individual if trava == TRAVA_INDIVIDUAL else self.territorial
        return SaldoInsuficiente(
            trava=trava, rubrica=self.rubrica.slug, disponivel=check.saldo, solicitado=self.valor,
            detail=check.motivo_bloqueio, solicitacao_id=solicitacao_id,
        )


def faixas_antes_e_depois(
    *, comprometido: Decimal, total: Decimal, delta: Decimal, limiares: "orcamento_service.LimiaresSemaforo",
) -> tuple[str, str]:
    antes = orcamento_service.percentual_comprometido(comprometido, total)
    depois = orcamento_service.percentual_comprometido(comprometido + delta, total)
    return (
        orcamento_service.faixa_semaforo(antes, limiares),
        orcamento_service.faixa_semaforo(depois, limiares),
    )


_SEM_SEMAFORO = {"semaforo_atual": None, "semaforo_apos": None}


def _semaforos(*, comprometido: Decimal, total: Decimal, valor: Decimal, limiares) -> dict:
    atual, apos = faixas_antes_e_depois(comprometido=comprometido, total=total, delta=valor, limiares=limiares)
    return {"semaforo_atual": atual, "semaforo_apos": apos}


def _semaforos_individual(*, limite, valor: Decimal, limiares) -> dict:
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
    limiares = orcamento_service.limiares_semaforo()
    return {
        "individual": {
            "disponivel": check.individual.disponivel,
            "saldo": check.individual.saldo,
            "motivo_bloqueio": check.individual.motivo_bloqueio,
            "acao_sugerida": check.individual.acao_sugerida,
            **_semaforos_individual(limite=check.individual.limite, valor=valor, limiares=limiares),
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
    if nivel == orcamento_service.Nivel.NACIONAL:
        return list(notifications_service.usuarios_por_perfil("ugp"))
    if nivel == orcamento_service.Nivel.ESTADUAL:
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
        limiares=orcamento_service.limiares_semaforo(),
    )
    if _ORDEM_SEMAFORO[depois] > _ORDEM_SEMAFORO[antes]:
        notifications_service.notificar_mudanca_semaforo(
            usuarios=usuarios, demand=demand, rubrica_nome=rubrica_nome, trava=trava, semaforo=depois,
        )


def _notificar_pool_se_piorou(movimento: "orcamento_service.MovimentoPool", *, demand, rubrica_nome) -> None:
    if movimento.allocation is None:
        return
    _notificar_se_piorou(
        usuarios=_destinatarios_saldo_territorial(
            nivel=movimento.nivel, estado_sigla=movimento.estado_sigla, territorio=movimento.territorio,
        ),
        demand=demand, rubrica_nome=rubrica_nome, trava=TRAVA_TERRITORIAL,
        comprometido_antes=movimento.comprometido_antes,
        comprometido_depois=movimento.allocation.valor_comprometido, limite=movimento.allocation.valor_alocado,
    )


def _checar_individual(*, solicitante, rubrica, valor: Decimal, consumo_previo: Decimal = ZERO) -> TravaCheck:
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    if limite is None:
        saldo, bloqueado = ZERO, True
    else:
        saldo = limite.saldo_disponivel - consumo_previo
        bloqueado = (saldo <= ZERO and consumo_previo <= ZERO) or valor > saldo
    if not bloqueado:
        return TravaCheck(disponivel=True, saldo=saldo, motivo_bloqueio=None, limite=limite)
    return TravaCheck(
        disponivel=False, saldo=saldo, limite=limite,
        motivo_bloqueio=_mensagem_individual(limite=limite, saldo=saldo, valor=valor, consumo_previo=consumo_previo),
        acao_sugerida=ACAO_SUGERIDA[TRAVA_INDIVIDUAL],
    )


def verificar_duas_travas(
    *, solicitante, rubrica, valor: Decimal, demand_request=None, activity=None, consumo_previo: Decimal = ZERO,
) -> DuasTravasCheck:
    """Somente leitura — não reserva nada. O pool é localizado pela atividade
    de `demand_request` ou por `activity`, quando ainda não há solicitação.

    `consumo_previo`: quanto outras solicitações da mesma operação, na mesma
    rubrica, já vão reservar antes desta. Sai do saldo das duas travas — o
    limite individual e a alocação territorial são os mesmos para todas."""
    individual = _checar_individual(
        solicitante=solicitante, rubrica=rubrica, valor=valor, consumo_previo=consumo_previo,
    )
    territorial = orcamento_service.consultar_pool(
        solicitante=solicitante, rubrica=rubrica, valor=valor, demand_request=demand_request,
        activity=activity, consumo_previo=consumo_previo,
    )
    return DuasTravasCheck(individual=individual, territorial=territorial, rubrica=rubrica, valor=valor)


def _reler_reserva(demand_request) -> None:
    """Chamada já com o limite travado: todo movimento da reserva trava o
    limite antes, então o estado relido aqui não muda até o commit."""
    demand_request.refresh_from_db(fields=["valor_reservado", "valor_executado"])


def _gravar_reserva(demand_request, **campos) -> None:
    """Grava só o estado da reserva, depois do pool: a solicitação é a última da
    ordem de lock (`backend/docs/orcamento.md`)."""
    DemandRequest.objects.filter(pk=demand_request.pk).update(**campos)
    for campo, valor in campos.items():
        setattr(demand_request, campo, valor)


def _registrar_movimento_individual(
    *, acao: str, entidade_id: str, usuario, valores_anteriores: dict | None = None, valores_novos: dict | None = None,
) -> None:
    contexto = get_audit_context()
    AuditLog.objects.create(
        user=usuario, acao=acao, modulo="sgd", entidade=_ENTIDADE_LIMITE, entidade_id=entidade_id,
        valores_anteriores=valores_anteriores or {}, valores_novos=valores_novos or {},
        ip=contexto["ip"], user_agent=contexto["user_agent"],
    )


@transaction.atomic
def reservar_duas_travas(*, demand_request, usuario) -> None:
    """Idempotente por `demand_request.pk`."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor = demand_request.valor_estimado

    entidade_id = str(demand_request.pk)
    limite = DemandIndividualLimit.objects.select_for_update().filter(
        solicitante=solicitante, rubrica=rubrica,
    ).first()
    if limite is None:
        # Removido depois da pré-checagem: mesma resposta que ela daria.
        raise _bloqueio_individual(
            rubrica=rubrica, limite=None, saldo=ZERO, valor=valor, solicitacao_id=demand_request.pk,
        )
    comprometido_individual_antes = limite.valor_comprometido
    _reler_reserva(demand_request)
    # Executada, a reserva já foi convertida: submeter de novo não a refaz.
    reservou = demand_request.valor_executado is None and not demand_request.reserva_ativa
    if reservou:
        # Reconfere o saldo com a linha já travada (select_for_update acima)
        # — sem isso, duas reservas concorrentes que passaram no
        # verificar_duas_travas (antes do lock) comprometeriam o limite além
        # do valor_limite.
        if valor > limite.saldo_disponivel:
            raise _bloqueio_individual(
                rubrica=rubrica, limite=limite, saldo=limite.saldo_disponivel, valor=valor,
                solicitacao_id=demand_request.pk,
            )
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

    movimento = orcamento_service.reservar_pool(
        solicitante=solicitante, rubrica=rubrica, valor=valor, demand_request=demand_request, usuario=usuario,
    )
    _notificar_pool_se_piorou(movimento, demand=demand_request.demanda, rubrica_nome=rubrica.nome)
    if reservou:
        _gravar_reserva(demand_request, valor_reservado=valor)


@transaction.atomic
def ajustar_duas_travas(
    *, demand_request, novo_valor: Decimal, usuario, ignorar_limite_individual: bool = False,
) -> None:
    """`ignorar_limite_individual=True` autoriza um excedente pontual (RF16) sem
    alterar `valor_limite` — usada só pelo fluxo de remanejamento emergencial da UGP.

    Reutilizável mais de uma vez para a mesma solicitação (autorização com
    valor ajustado, depois edição em Devolvida, depois nova autorização
    etc.) — cada chamada parte do `valor_reservado` relido sob o lock, então
    repetir o mesmo `novo_valor` não move o saldo de novo."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    _reler_reserva(demand_request)
    if not demand_request.reserva_ativa:
        raise RegraDeNegocio(f"A solicitação #{demand_request.pk} não tem reserva ativa para ajustar.")
    valor_anterior = demand_request.valor_reservado
    diferenca = novo_valor - valor_anterior
    comprometido_individual_antes = limite.valor_comprometido
    if diferenca != ZERO:
        if not ignorar_limite_individual and diferenca > ZERO and diferenca > limite.saldo_disponivel:
            raise SaldoInsuficiente(
                trava=TRAVA_INDIVIDUAL, rubrica=rubrica.slug, disponivel=limite.saldo_disponivel,
                solicitado=diferenca, solicitacao_id=demand_request.pk,
                detail=com_orientacao(
                    f"Limite individual insuficiente para o ajuste: {formatar_brl(limite.saldo_disponivel)} "
                    f"disponível, {formatar_brl(diferenca)} a mais solicitado.",
                    ORIENTACAO_INDIVIDUAL,
                ),
            )
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

    movimento = orcamento_service.ajustar_pool(
        solicitante=solicitante, rubrica=rubrica, valor=novo_valor, demand_request=demand_request, usuario=usuario,
    )
    _notificar_pool_se_piorou(movimento, demand=demand_request.demanda, rubrica_nome=rubrica.nome)
    if diferenca != ZERO:
        _gravar_reserva(demand_request, valor_reservado=novo_valor)


@transaction.atomic
def liberar_duas_travas(*, demand_request, usuario, motivo: str) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().filter(
        solicitante=solicitante, rubrica=rubrica,
    ).first()
    # Só libera com reserva ativa agora — cancelar um Rascunho (nunca
    # reservado) ou liberar duas vezes seguidas não pode decrementar o
    # comprometido de novo. E libera o `valor_reservado`, não `valor_estimado`,
    # que fica no valor original depois de um ajuste.
    _reler_reserva(demand_request)
    liberou = demand_request.reserva_ativa
    if liberou and limite is not None:
        valor = demand_request.valor_reservado
        limite.valor_comprometido -= valor
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="liberacao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={"limite_id": limite.pk, "valor": str(valor)},
        )

    orcamento_service.liberar_pool(
        solicitante=solicitante, rubrica=rubrica, demand_request=demand_request, usuario=usuario, motivo=motivo,
    )
    if liberou:
        _gravar_reserva(demand_request, valor_reservado=ZERO)


@transaction.atomic
def liberar_duas_travas_em_lote(solicitacoes, *, usuario, motivo: str) -> None:
    """Libera as reservas de solicitações de várias demandas, de vários solicitantes.
    Liberar uma por uma travaria a alocação de um solicitante antes do limite do
    seguinte; por isso, rubrica a rubrica, trava antes todos os limites e depois todas
    as alocações envolvidas (ordem de `backend/docs/orcamento.md`)."""
    solicitacoes = sorted(solicitacoes, key=lambda s: (s.rubrica_id, s.pk))
    for rubrica_id, grupo in groupby(solicitacoes, key=lambda s: s.rubrica_id):
        grupo = list(grupo)
        _travar_em_ordem_de_pk(DemandIndividualLimit.objects.filter(
            rubrica_id=rubrica_id, solicitante_id__in={s.demanda.solicitante_id for s in grupo},
        ))
        orcamento_service.travar_pools_das_reservas(grupo)
        for solicitacao in grupo:
            liberar_duas_travas(demand_request=solicitacao, usuario=usuario, motivo=motivo)


def _travar_em_ordem_de_pk(queryset) -> None:
    list(queryset.select_for_update().order_by("pk").values_list("pk", flat=True))


@transaction.atomic
def executar_duas_travas(*, demand_request, valor_pago: Decimal, usuario) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    _reler_reserva(demand_request)
    executou = demand_request.valor_executado is None
    if executou:
        valor_reservado = demand_request.valor_reservado
        limite.valor_comprometido -= valor_reservado
        limite.valor_executado += valor_pago
        limite.save(update_fields=["valor_comprometido", "valor_executado"])
        _registrar_movimento_individual(
            acao="execucao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={"valor_pago": str(valor_pago), "diferenca_liberada": str(valor_reservado - valor_pago)},
        )

    orcamento_service.executar_pool(
        solicitante=solicitante, rubrica=rubrica, valor=valor_pago, demand_request=demand_request, usuario=usuario,
    )
    if executou:
        _gravar_reserva(demand_request, valor_executado=valor_pago)


@transaction.atomic
def autorizar_excedente(*, demand_request, origem_allocation, valor_excedente: Decimal,
                         justificativa: str, usuario) -> None:
    if not justificativa:
        raise JustificativaObrigatoria("Obrigatória para autorizar excedente.")
    if origem_allocation.nivel not in (orcamento_service.Nivel.ESTADUAL, orcamento_service.Nivel.NACIONAL):
        raise RegraDeNegocio(
            "Remanejamento emergencial só pode vir de saldo estadual ou nacional.",
            campo="origem_allocation",
        )

    destino = orcamento_service.consultar_pool(
        solicitante=demand_request.demanda.solicitante, rubrica=demand_request.rubrica, valor=ZERO,
        demand_request=demand_request,
    ).allocation
    if destino is None:
        raise RegraDeNegocio("Nenhuma alocação territorial encontrada para remanejar.")

    orcamento_service.remanejar(
        origem=origem_allocation, destino=destino, valor=valor_excedente,
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
