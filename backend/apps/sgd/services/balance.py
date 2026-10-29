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
    RegraDeNegocio,
    SaldoInsuficiente,
    TransicaoInvalida,
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


def reler_reserva(demand_request) -> None:
    """Relê do banco o estado da reserva. Com o limite travado, o valor não muda
    até o commit: todo movimento da reserva trava o limite antes. Sem o lock,
    serve para escolher o caminho, e a operação de saldo confere de novo.

    O limite é travado pela rubrica que quem chama leu antes. Se a solicitação foi
    removida ou mudou de rubrica enquanto esperava o lock, mexer no saldo agora
    tiraria a reserva do limite errado: a operação é recusada."""
    atual = DemandRequest.objects.filter(pk=demand_request.pk).values_list(
        "rubrica_id", "valor_reservado", "valor_executado", "valor_excedente",
    ).first()
    if atual is None:
        raise TransicaoInvalida(
            f"A solicitação #{demand_request.pk} foi removida durante a operação. Recarregue e tente de novo."
        )
    (
        rubrica_id, demand_request.valor_reservado, demand_request.valor_executado, demand_request.valor_excedente,
    ) = atual
    if rubrica_id != demand_request.rubrica_id:
        raise TransicaoInvalida(
            f"A solicitação #{demand_request.pk} mudou de rubrica durante a operação. Recarregue e tente de novo."
        )


def _travar_limite(*, solicitante_id, rubrica_id) -> DemandIndividualLimit | None:
    """`of=("self",)`: o `ordering` do model é por solicitante e rubrica, e o
    `.first()` levaria o JOIN com `core_user` e com a rubrica para dentro do FOR
    UPDATE. A linha do solicitante ficaria travada, e o commit de qualquer outra
    transação que gravou algo apontando para ele (notificação, auditoria, etapa)
    esperaria este lock na checagem da FK."""
    return DemandIndividualLimit.objects.select_for_update(of=("self",)).filter(
        solicitante_id=solicitante_id, rubrica_id=rubrica_id,
    ).first()


def reler_reserva_travada(demand_request) -> None:
    """Trava o limite da solicitação e relê o estado da reserva, que daí até o
    commit não muda."""
    _travar_limite(solicitante_id=demand_request.demanda.solicitante_id, rubrica_id=demand_request.rubrica_id)
    reler_reserva(demand_request)


def _mover_reserva(demand_request, *, adiar: bool, **campos) -> None:
    for campo, valor in campos.items():
        setattr(demand_request, campo, valor)
    if not adiar:
        gravar_estado_da_reserva([demand_request])


def gravar_estado_da_reserva(solicitacoes, *, outros_campos=()) -> None:
    """Grava o estado da reserva já aplicado em memória, mais `outros_campos`. A
    solicitação é a última da ordem de lock (`backend/docs/orcamento.md`): quem
    move o saldo de várias solicitações e depois trava a `Demand` passa
    `adiar_gravacao=True` e chama isto no fim. Gravar cada uma logo depois do seu
    pool deixaria a linha travada antes do limite da rubrica seguinte e da
    `Demand`, e a decisão de recurso extra, que trava `Demand` e depois as
    solicitações, fecharia um ciclo."""
    campos = ("valor_reservado", "valor_executado", "valor_excedente", *outros_campos)
    for solicitacao in sorted(solicitacoes, key=lambda s: s.pk):
        DemandRequest.objects.filter(pk=solicitacao.pk).update(
            **{campo: getattr(solicitacao, campo) for campo in campos},
        )


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
def reservar_duas_travas(*, demand_request, usuario, adiar_gravacao: bool = False) -> None:
    """Idempotente por `demand_request.pk`. Com `adiar_gravacao`, ver
    `gravar_estado_da_reserva`."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    valor = demand_request.valor_estimado

    entidade_id = str(demand_request.pk)
    limite = _travar_limite(solicitante_id=solicitante.pk, rubrica_id=rubrica.pk)
    if limite is None:
        # Removido depois da pré-checagem: mesma resposta que ela daria.
        raise _bloqueio_individual(
            rubrica=rubrica, limite=None, saldo=ZERO, valor=valor, solicitacao_id=demand_request.pk,
        )
    comprometido_individual_antes = limite.valor_comprometido
    reler_reserva(demand_request)
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
        _mover_reserva(demand_request, adiar=adiar_gravacao, valor_reservado=valor, valor_excedente=ZERO)


@transaction.atomic
def ajustar_duas_travas(
    *, demand_request, novo_valor: Decimal, usuario, excedente: Decimal = ZERO, adiar_gravacao: bool = False,
) -> None:
    """`excedente` é a parte do aumento já coberta por remanejamento emergencial
    (`remanejamento.cobrir_excedente`): não entra no limite individual, que não
    tem `valor_limite` alterado. Numa redução, sai primeiro o excedente e só o
    resto volta ao limite.

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
    reler_reserva(demand_request)
    if not demand_request.reserva_ativa:
        raise RegraDeNegocio(f"A solicitação #{demand_request.pk} não tem reserva ativa para ajustar.")
    valor_anterior = demand_request.valor_reservado
    excedente_anterior = demand_request.valor_excedente
    diferenca = novo_valor - valor_anterior
    if excedente > max(diferenca, ZERO):
        raise ValueError("O excedente não pode passar do aumento da reserva.")
    if diferenca >= ZERO:
        no_limite = diferenca - excedente
        excedente_novo = excedente_anterior + excedente
    else:
        sai_do_excedente = min(-diferenca, excedente_anterior)
        no_limite = diferenca + sai_do_excedente
        excedente_novo = excedente_anterior - sai_do_excedente

    comprometido_individual_antes = limite.valor_comprometido
    if no_limite > ZERO and no_limite > limite.saldo_disponivel:
        raise SaldoInsuficiente(
            trava=TRAVA_INDIVIDUAL, rubrica=rubrica.slug, disponivel=limite.saldo_disponivel,
            solicitado=no_limite, solicitacao_id=demand_request.pk,
            detail=com_orientacao(
                f"Limite individual insuficiente para o ajuste: {formatar_brl(limite.saldo_disponivel)} "
                f"disponível, {formatar_brl(no_limite)} a mais solicitado.",
                ORIENTACAO_INDIVIDUAL,
            ),
        )
    if diferenca != ZERO:
        limite.valor_comprometido += no_limite
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="ajuste", entidade_id=entidade_id, usuario=usuario,
            valores_anteriores={"valor": str(valor_anterior), "excedente": str(excedente_anterior)},
            valores_novos={"valor": str(novo_valor), "excedente": str(excedente_novo)},
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
        _mover_reserva(
            demand_request, adiar=adiar_gravacao, valor_reservado=novo_valor, valor_excedente=excedente_novo,
        )


@transaction.atomic
def liberar_duas_travas(*, demand_request, usuario, motivo: str, adiar_gravacao: bool = False) -> None:
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = _travar_limite(solicitante_id=solicitante.pk, rubrica_id=rubrica.pk)
    # Só libera com reserva ativa agora — cancelar um Rascunho (nunca
    # reservado) ou liberar duas vezes seguidas não pode decrementar o
    # comprometido de novo. E libera o `valor_reservado`, não `valor_estimado`,
    # que fica no valor original depois de um ajuste.
    reler_reserva(demand_request)
    liberou = demand_request.reserva_ativa
    if liberou and limite is not None:
        # O excedente nunca esteve no limite: não volta como saldo individual.
        valor = demand_request.valor_no_limite
        limite.valor_comprometido -= valor
        limite.save(update_fields=["valor_comprometido"])
        _registrar_movimento_individual(
            acao="liberacao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={
                "limite_id": limite.pk, "valor": str(valor), "excedente": str(demand_request.valor_excedente),
            },
        )

    orcamento_service.liberar_pool(
        solicitante=solicitante, rubrica=rubrica, demand_request=demand_request, usuario=usuario, motivo=motivo,
    )
    if liberou:
        _mover_reserva(demand_request, adiar=adiar_gravacao, valor_reservado=ZERO, valor_excedente=ZERO)


@transaction.atomic
def liberar_duas_travas_em_lote(solicitacoes, *, usuario, motivo: str, adiar_gravacao: bool = False) -> None:
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
            liberar_duas_travas(
                demand_request=solicitacao, usuario=usuario, motivo=motivo, adiar_gravacao=adiar_gravacao,
            )


def _travar_em_ordem_de_pk(queryset) -> None:
    list(queryset.select_for_update().order_by("pk").values_list("pk", flat=True))


@transaction.atomic
def executar_duas_travas(*, demand_request, valor_pago: Decimal, usuario, adiar_gravacao: bool = False) -> bool:
    """Devolve False quando a reserva já tinha sido executada: o saldo não muda."""
    rubrica = demand_request.rubrica
    solicitante = demand_request.demanda.solicitante
    entidade_id = str(demand_request.pk)

    limite = DemandIndividualLimit.objects.select_for_update().get(
        solicitante=solicitante, rubrica=rubrica,
    )
    reler_reserva(demand_request)
    executou = demand_request.valor_executado is None
    if executou:
        # Do pago, o limite individual executa só até a parte que comprometeu; o
        # resto saiu do excedente, e o excedente que sobrar não vira saldo individual.
        no_limite = demand_request.valor_no_limite
        executado_no_limite = min(valor_pago, no_limite)
        limite.valor_comprometido -= no_limite
        limite.valor_executado += executado_no_limite
        limite.save(update_fields=["valor_comprometido", "valor_executado"])
        _registrar_movimento_individual(
            acao="execucao", entidade_id=entidade_id, usuario=usuario,
            valores_novos={
                "valor_pago": str(valor_pago), "executado_no_limite": str(executado_no_limite),
                "diferenca_liberada": str(no_limite - executado_no_limite),
            },
        )

    orcamento_service.executar_pool(
        solicitante=solicitante, rubrica=rubrica, valor=valor_pago, demand_request=demand_request, usuario=usuario,
    )
    if executou:
        _mover_reserva(demand_request, adiar=adiar_gravacao, valor_executado=valor_pago)
    return executou

