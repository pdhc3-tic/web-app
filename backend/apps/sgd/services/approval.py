from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.user import User
from apps.core.services.permissions import user_has_role, user_states
from apps.sgd.models.demand import STATUS_CANCELAVEIS_PELO_SOLICITANTE, STATUS_TRANSITIONS
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.demand_request import rubrica_slug_para_tipo


class TransicaoInvalidaError(DRFValidationError):
    # DRF ValidationError, não Django — levantar direto da view já vira 400
    # sem precisar de try/except de tradução.
    def __init__(self, message):
        super().__init__({"status": message})


class JustificativaObrigatoriaError(DRFValidationError):
    def __init__(self, message):
        super().__init__({"justificativa": message})


def validar_transicao(demand, novo_status: str) -> None:
    permitidos = STATUS_TRANSITIONS.get(demand.status, set())
    if novo_status not in permitidos:
        raise TransicaoInvalidaError(
            f"Transição inválida: '{demand.status}' → '{novo_status}'. "
            f"Transições permitidas: {sorted(permitidos) if permitidos else ['nenhuma (estado terminal)']}"
        )


def transition(demand, novo_status: str) -> None:
    validar_transicao(demand, novo_status)
    demand.status = novo_status


def pode_cancelar(demand, usuario) -> bool:
    return demand.solicitante_id == usuario.pk and demand.status in STATUS_CANCELAVEIS_PELO_SOLICITANTE


def demand_visibility_scope(user) -> Q | None:
    if user_has_role(user, "super-admin") or user_has_role(user, "ugp") or user_has_role(user, "fgd"):
        return None

    if user_has_role(user, "articulador-estadual"):
        # RF18: só "Submetidas" do seu estado, além das próprias e das que
        # ele já decidiu (para manter acesso ao que já pré-autorizou/devolveu).
        states = user_states(user)
        if not states:
            return Q(solicitante=user) | Q(etapas__responsavel=user)
        return (
            Q(solicitante=user)
            | Q(etapas__responsavel=user)
            | Q(status="submetida", activity__municipio__state__sigla__in=states)
        )

    return Q(solicitante=user)


def responsaveis_pela_etapa_atual(demand):
    if demand.status in {"rascunho", "devolvida"}:
        return User.objects.filter(pk=demand.solicitante_id)
    if demand.status == "submetida":
        sigla = demand.activity.municipio.state.sigla
        return notifications_service.usuarios_articuladores_do_estado(sigla)
    if demand.status == "pre_autorizada":
        return notifications_service.usuarios_por_perfil("ugp")
    if demand.status in {"autorizada", "em_atendimento"}:
        return notifications_service.usuarios_por_perfil("fgd")
    return User.objects.none()


def preview_impacto(demand_request, valor: Decimal) -> dict:
    solicitante = demand_request.demanda.solicitante
    rubrica = demand_request.rubrica
    meta = demand_request.meta

    check = balance_service.verificar_duas_travas(
        solicitante=solicitante, rubrica=rubrica, meta=meta, valor=valor,
    )

    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    individual = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    if limite is not None:
        individual["semaforo_antes"] = balance_service.semaforo_sgd(
            balance_service.percentual_comprometido(limite.valor_comprometido, limite.valor_limite)
        )
        individual["semaforo_apos"] = balance_service.semaforo_sgd(
            balance_service.percentual_comprometido(limite.valor_comprometido + valor, limite.valor_limite)
        )
        individual["saldo_apos"] = limite.saldo_disponivel - valor

    territorial = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    allocation = check.territorial.allocation
    if allocation is not None:
        territorial["semaforo_antes"] = balance_service.semaforo_sgd(
            balance_service.percentual_comprometido(allocation.valor_comprometido, allocation.valor_alocado)
        )
        territorial["semaforo_apos"] = balance_service.semaforo_sgd(
            balance_service.percentual_comprometido(allocation.valor_comprometido + valor, allocation.valor_alocado)
        )
        territorial["saldo_apos"] = check.territorial.saldo - valor

    return {
        "disponivel": check.disponivel,
        "trava_bloqueada": check.trava_bloqueada,
        "individual": individual,
        "territorial": territorial,
    }


def alerta_rubrica_fora_do_previsto(demand_request) -> bool:
    # Não há campo de "rubricas previstas da Ação" no SGP — usa o mapeamento
    # tipo→rubrica como proxy do esperado.
    esperado = rubrica_slug_para_tipo(demand_request.tipo)
    return demand_request.rubrica.slug != esperado


@transaction.atomic
def pre_autorizar(demand, *, responsavel) -> object:
    transition(demand, "pre_autorizada")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="pre_autorizacao", responsavel=responsavel, acao="aprovado",
    )
    notifications_service.notificar_pre_autorizacao(demand, notifications_service.usuarios_por_perfil("ugp"))
    return demand


@transaction.atomic
def devolver(demand, *, responsavel, justificativa: str) -> object:
    if not justificativa:
        raise JustificativaObrigatoriaError("Obrigatória para devolver a demanda.")
    transition(demand, "devolvida")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="pre_autorizacao", responsavel=responsavel,
        acao="devolvido", justificativa=justificativa,
    )
    notifications_service.notificar_devolucao(demand)
    return demand


@transaction.atomic
def autorizar(demand, *, responsavel, ajustes: dict | None = None, excedente_autorizado: bool = False) -> object:
    """`ajustes`: {demand_request_id: novo_valor}."""
    ajustes = ajustes or {}
    for solicitacao in demand.solicitacoes.all():
        novo_valor = ajustes.get(solicitacao.pk, solicitacao.valor_estimado)
        if novo_valor != solicitacao.valor_estimado:
            balance_service.ajustar_duas_travas(
                demand_request=solicitacao, novo_valor=novo_valor, usuario=responsavel,
            )
        solicitacao.valor_autorizado = novo_valor
        solicitacao.save(update_fields=["valor_autorizado"])

    transition(demand, "autorizada")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="autorizacao", responsavel=responsavel,
        acao="aprovado", excedente_autorizado=excedente_autorizado,
    )
    notifications_service.notificar_autorizacao(demand, notifications_service.usuarios_por_perfil("fgd"))
    return demand


@transaction.atomic
def recusar(demand, *, responsavel, justificativa: str) -> object:
    if not justificativa:
        raise JustificativaObrigatoriaError("Obrigatória para recusar a demanda.")
    for solicitacao in demand.solicitacoes.all():
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=responsavel, motivo="Demanda recusada pela UGP.",
        )
    transition(demand, "recusada")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="autorizacao", responsavel=responsavel,
        acao="recusado", justificativa=justificativa,
    )
    notifications_service.notificar_recusa(demand)
    return demand


@transaction.atomic
def atender(demand, *, responsavel) -> object:
    transition(demand, "em_atendimento")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="atendimento", responsavel=responsavel, acao="atendido",
    )
    notifications_service.notificar_em_atendimento(demand)
    return demand


@transaction.atomic
def concluir(demand, *, responsavel, valores_pagos: dict) -> object:
    """`valores_pagos`: {demand_request_id: valor_pago}."""
    for solicitacao in demand.solicitacoes.all():
        if solicitacao.pk not in valores_pagos:
            raise DRFValidationError({
                "valores_pagos": f"Valor pago obrigatório para a solicitação #{solicitacao.pk}."
            })
        valor_pago = valores_pagos[solicitacao.pk]
        balance_service.executar_duas_travas(
            demand_request=solicitacao, valor_pago=valor_pago, usuario=responsavel,
        )
        solicitacao.valor_pago = valor_pago
        solicitacao.save(update_fields=["valor_pago"])

    transition(demand, "concluida")
    demand.save(update_fields=["status", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="atendimento", responsavel=responsavel, acao="atendido",
    )
    notifications_service.notificar_conclusao(demand)
    return demand
