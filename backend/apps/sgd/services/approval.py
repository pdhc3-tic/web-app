from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.user import User
from apps.core.services.permissions import user_has_role, user_states
from apps.sgd.models.demand import STATUS_CANCELAVEIS_PELO_SOLICITANTE, STATUS_TRANSITIONS
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgp.services import budget as budget_service


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
    demand.status_alterado_em = timezone.now()


def pode_cancelar(demand, usuario) -> bool:
    return demand.solicitante_id == usuario.pk and demand.status in STATUS_CANCELAVEIS_PELO_SOLICITANTE


def demand_visibility_scope(user) -> Q | None:
    if user_has_role(user, "super-admin") or user_has_role(user, "ugp") or user_has_role(user, "fgd"):
        return None

    if user_has_role(user, "articulador-estadual"):
        # RF18: só "Submetidas" do seu estado, além das próprias e das que
        # ele já decidiu (para manter acesso ao que já pré-autorizou/devolveu).
        # `user_states` já devolve todos os estados pra um perfil global (sem
        # território específico) — não precisa de ramo especial pra isso, e
        # com states vazio (nenhum território cadastrado) o `sigla__in` some
        # sozinho, mesmo resultado do notifications_service para esse perfil.
        states = user_states(user)
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
    """`valor` é o novo valor proposto pelo aprovador — a solicitação já está
    reservada (pré-autorizada/autorizada) pelo valor atual, então só o delta
    entre os dois pesa no saldo; contar `valor` inteiro de novo dobraria a
    reserva já feita."""
    solicitante = demand_request.demanda.solicitante
    rubrica = demand_request.rubrica
    meta = demand_request.meta
    valor_reservado = demand_request.valor_autorizado or demand_request.valor_estimado
    delta = valor - valor_reservado

    if delta > Decimal("0"):
        check = balance_service.verificar_duas_travas(
            solicitante=solicitante, rubrica=rubrica, meta=meta, valor=delta,
        )
        disponivel, trava_bloqueada, allocation = check.disponivel, check.trava_bloqueada, check.territorial.allocation
    else:
        # Reduzir o valor autorizado nunca bloqueia — está liberando saldo.
        nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(solicitante)
        allocation = budget_service.saldo_para_consulta(
            meta_id=meta.pk, rubrica_slug=rubrica.slug, nivel=nivel,
            estado_sigla=estado_sigla, territorio=territorio, valor=Decimal("0"),
        ).allocation
        disponivel, trava_bloqueada = True, None

    limiares = budget_service.limiares_semaforo()
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    individual = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    if limite is not None:
        individual["semaforo_antes"], individual["semaforo_apos"] = balance_service.faixas_antes_e_depois(
            comprometido=limite.valor_comprometido, total=limite.valor_limite, delta=delta, limiares=limiares,
        )
        individual["saldo_apos"] = limite.saldo_disponivel - delta

    territorial = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    if allocation is not None:
        territorial["semaforo_antes"], territorial["semaforo_apos"] = balance_service.faixas_antes_e_depois(
            comprometido=allocation.valor_comprometido, total=allocation.valor_alocado, delta=delta,
            limiares=limiares,
        )
        territorial["saldo_apos"] = allocation.valor_alocado - allocation.valor_comprometido - delta

    return {
        "disponivel": disponivel,
        "trava_bloqueada": trava_bloqueada,
        "individual": individual,
        "territorial": territorial,
    }


def alerta_rubrica_fora_do_previsto(demand_request) -> bool:
    previstas = demand_request.demanda.activity.acao.rubricas_previstas
    if not previstas.exists():
        # Sem previsão cadastrada na Ação — não é falso positivo, é "sem opinião".
        return False
    return not previstas.filter(pk=demand_request.rubrica_id).exists()


def _exigir_pode_decidir_articulador(demand, responsavel) -> None:
    """Segrega quem submete de quem decide (RF18/RF19): o Articulador não
    pode pré-autorizar/devolver a própria demanda nem uma de fora do estado
    em que atua — mesmo estando no queryset de visibilidade dele (que
    inclui as próprias demandas, para ele continuar vendo o que já decidiu)."""
    if demand.solicitante_id == responsavel.pk:
        raise PermissionDenied("Você não pode decidir sobre a própria demanda.")
    estado_sigla = demand.activity.municipio.state.sigla
    if estado_sigla not in user_states(responsavel):
        raise PermissionDenied("Demanda fora do seu estado de atuação.")


@transaction.atomic
def pre_autorizar(demand, *, responsavel) -> object:
    _exigir_pode_decidir_articulador(demand, responsavel)
    transition(demand, "pre_autorizada")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="pre_autorizacao", responsavel=responsavel, acao="aprovado",
    )
    notifications_service.notificar_pre_autorizacao(demand, notifications_service.usuarios_por_perfil("ugp"))
    return demand


@transaction.atomic
def devolver(demand, *, responsavel, justificativa: str) -> object:
    _exigir_pode_decidir_articulador(demand, responsavel)
    if not justificativa:
        raise JustificativaObrigatoriaError("Obrigatória para devolver a demanda.")
    transition(demand, "devolvida")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="pre_autorizacao", responsavel=responsavel,
        acao="devolvido", justificativa=justificativa,
    )
    notifications_service.notificar_devolucao(demand)
    return demand


@transaction.atomic
def autorizar(
    demand, *, responsavel, ajustes: dict | None = None,
    excedente_autorizado: bool = False, justificativa: str = "",
) -> object:
    """`ajustes`: {demand_request_id: novo_valor}."""
    if excedente_autorizado and not justificativa:
        raise JustificativaObrigatoriaError("Obrigatória para autorizar excedendo o limite individual (RF16).")

    ajustes = ajustes or {}
    solicitacoes_pks = set(demand.solicitacoes.values_list("pk", flat=True))
    ids_desconhecidos = set(ajustes) - solicitacoes_pks
    if ids_desconhecidos:
        raise DRFValidationError({
            "ajustes": f"Solicitação(ões) {sorted(ids_desconhecidos)} não pertence(m) a esta demanda."
        })

    for solicitacao in demand.solicitacoes.order_by("rubrica_id", "pk"):
        novo_valor = ajustes.get(solicitacao.pk, solicitacao.valor_estimado)
        if novo_valor != solicitacao.valor_estimado:
            balance_service.ajustar_duas_travas(
                demand_request=solicitacao, novo_valor=novo_valor, usuario=responsavel,
                ignorar_limite_individual=excedente_autorizado,
            )
        solicitacao.valor_autorizado = novo_valor
        solicitacao.save(update_fields=["valor_autorizado"])

    transition(demand, "autorizada")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="autorizacao", responsavel=responsavel,
        acao="aprovado", excedente_autorizado=excedente_autorizado, justificativa=justificativa,
    )
    notifications_service.notificar_autorizacao(demand, notifications_service.usuarios_por_perfil("fgd"))
    return demand


@transaction.atomic
def recusar(demand, *, responsavel, justificativa: str) -> object:
    if not justificativa:
        raise JustificativaObrigatoriaError("Obrigatória para recusar a demanda.")
    for solicitacao in demand.solicitacoes.order_by("rubrica_id", "pk"):
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=responsavel, motivo="Demanda recusada pela UGP.",
        )
    transition(demand, "recusada")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="autorizacao", responsavel=responsavel,
        acao="recusado", justificativa=justificativa,
    )
    notifications_service.notificar_recusa(demand)
    return demand


@transaction.atomic
def atender(demand, *, responsavel) -> object:
    transition(demand, "em_atendimento")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="atendimento", responsavel=responsavel, acao="atendido",
    )
    notifications_service.notificar_em_atendimento(demand)
    return demand


@transaction.atomic
def concluir(demand, *, responsavel, valores_pagos: dict) -> object:
    """`valores_pagos`: {demand_request_id: valor_pago}."""
    for solicitacao in demand.solicitacoes.order_by("rubrica_id", "pk"):
        if solicitacao.pk not in valores_pagos:
            raise DRFValidationError({
                "valores_pagos": f"Valor pago obrigatório para a solicitação #{solicitacao.pk}."
            })
        valor_pago = valores_pagos[solicitacao.pk]
        valor_autorizado = solicitacao.valor_autorizado or solicitacao.valor_estimado
        if valor_pago > valor_autorizado:
            raise DRFValidationError({
                "valores_pagos": (
                    f"Valor pago (R$ {valor_pago}) não pode exceder o valor autorizado "
                    f"(R$ {valor_autorizado}) para a solicitação #{solicitacao.pk}."
                )
            })
        balance_service.executar_duas_travas(
            demand_request=solicitacao, valor_pago=valor_pago, usuario=responsavel,
        )
        solicitacao.valor_pago = valor_pago
        solicitacao.save(update_fields=["valor_pago"])

    transition(demand, "concluida")
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    ApprovalStep.objects.create(
        demanda=demand, etapa="atendimento", responsavel=responsavel, acao="atendido",
    )
    notifications_service.notificar_conclusao(demand)
    return demand
