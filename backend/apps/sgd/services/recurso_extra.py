"""Solicitação de Recurso Extra (SGP §6.6) e o remanejamento que a decisão da UGP pode disparar.

O pedido percorre a máquina de estados de `BudgetIncreaseRequest`. Aprovar eleva o
limite individual do solicitante na rubrica; se o pool territorial não cobrir o
valor, a UGP é alertada e pode remanejar de uma alocação estadual ou nacional na
própria decisão. A demanda bloqueada não é submetida sozinha: o limite maior só a
deixa passar nas duas travas quando o solicitante submeter de novo.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.signals.audit import get_audit_context
from apps.sgd.models import Demand, DemandIndividualLimit
from apps.sgd.models.demand import STATUS_EDITAVEIS
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.balance import _destinatarios_saldo_territorial
from apps.sgp.models import BudgetAllocation, BudgetIncreaseRequest, BudgetTransfer
from apps.sgp.services import budget as budget_service

Status = BudgetIncreaseRequest.Status
ZERO = Decimal("0")

ENTIDADE_PEDIDO = "BudgetIncreaseRequest"
ENTIDADE_LIMITE = "DemandIndividualLimit"
ENTIDADE_REMANEJAMENTO = "BudgetTransfer"

DECISOES = {
    "aprovar": Status.APROVADA,
    "aprovar_parcialmente": Status.APROVADA_PARCIALMENTE,
    "recusar": Status.RECUSADA,
}


def _saldo(allocation: BudgetAllocation) -> Decimal:
    return allocation.valor_alocado - allocation.valor_comprometido - allocation.valor_executado


def _exigir_transicao(pedido, para) -> None:
    if para not in pedido.get_transicoes_permitidas():
        permitidos = sorted(pedido.get_transicoes_permitidas())
        raise DRFValidationError({
            "status": (
                f"Transição inválida: '{pedido.status}' → '{para}'. "
                f"Transições permitidas: {permitidos or ['nenhuma (estado terminal)']}"
            )
        })


def _exigir_texto(valor: str, campo: str, mensagem: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise DRFValidationError({campo: mensagem})
    return valor


def _exigir_valor_positivo(valor: Decimal, campo: str = "valor_solicitado") -> None:
    if valor is None or valor <= ZERO:
        raise DRFValidationError({campo: "Deve ser maior que zero."})


def _mudar_status(pedido, para, usuario, acao: str, **campos) -> None:
    de = pedido.status
    _exigir_transicao(pedido, para)
    pedido.status = para
    for campo, valor in campos.items():
        setattr(pedido, campo, valor)
    pedido.save()
    auditoria_service.registrar_evento(
        acao=f"recurso_extra.{acao}", entidade=ENTIDADE_PEDIDO, entidade_id=pedido.pk, usuario=usuario,
        anteriores={"status": de}, novos={"status": para, "demanda": pedido.demanda_id},
    )


def _sigla_do_pedido(pedido) -> str | None:
    if pedido.activity_id is None:
        return None
    return pedido.activity.municipio.state.sigla


@transaction.atomic
def criar(*, demanda: Demand, rubrica, valor_solicitado: Decimal, justificativa: str,
          usuario, periodo_aplicacao: str = "", submeter: bool = True) -> BudgetIncreaseRequest:
    if demanda.status not in STATUS_EDITAVEIS:
        raise DRFValidationError({
            "demanda": "Só uma demanda em Rascunho ou Devolvida, a que o bloqueio impede de submeter, "
                       "pode pedir recurso extra."
        })
    if not demanda.solicitacoes.filter(rubrica=rubrica).exists():
        raise DRFValidationError({"rubrica": "A demanda não tem solicitação nesta rubrica."})
    _exigir_valor_positivo(valor_solicitado)
    justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória.")

    pedido = BudgetIncreaseRequest.objects.create(
        user=demanda.solicitante, rubrica=rubrica, valor_solicitado=valor_solicitado,
        periodo_aplicacao=periodo_aplicacao, activity=demanda.activity, demanda_id=str(demanda.pk),
        justificativa=justificativa,
    )
    auditoria_service.registrar_evento(
        acao="recurso_extra.criado", entidade=ENTIDADE_PEDIDO, entidade_id=pedido.pk, usuario=usuario,
        novos={
            "status": pedido.status, "demanda": pedido.demanda_id, "rubrica": rubrica.slug,
            "valor_solicitado": str(valor_solicitado),
        },
    )
    if submeter:
        submeter_pedido(pedido, usuario=usuario)
    return pedido


@transaction.atomic
def editar(pedido, *, usuario, valor_solicitado=None, justificativa=None, periodo_aplicacao=None):
    if pedido.status not in BudgetIncreaseRequest.EDITAVEIS:
        raise DRFValidationError({
            "status": f"Pedido em status '{pedido.get_status_display()}' não pode ser editado."
        })
    anteriores = {
        "valor_solicitado": str(pedido.valor_solicitado), "justificativa": pedido.justificativa,
        "periodo_aplicacao": pedido.periodo_aplicacao,
    }
    if valor_solicitado is not None:
        _exigir_valor_positivo(valor_solicitado)
        pedido.valor_solicitado = valor_solicitado
    if justificativa is not None:
        pedido.justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória.")
    if periodo_aplicacao is not None:
        pedido.periodo_aplicacao = periodo_aplicacao
    pedido.save()
    auditoria_service.registrar_evento(
        acao="recurso_extra.editado", entidade=ENTIDADE_PEDIDO, entidade_id=pedido.pk, usuario=usuario,
        anteriores=anteriores,
        novos={
            "valor_solicitado": str(pedido.valor_solicitado), "justificativa": pedido.justificativa,
            "periodo_aplicacao": pedido.periodo_aplicacao,
        },
    )
    return pedido


@transaction.atomic
def submeter_pedido(pedido, *, usuario):
    _mudar_status(pedido, Status.SUBMETIDA, usuario, "submetido")
    sigla = _sigla_do_pedido(pedido)
    if sigla:
        notifications_service.notificar_recurso_extra_submetido(
            pedido, notifications_service.usuarios_articuladores_do_estado(sigla),
        )
    return pedido


@transaction.atomic
def emitir_parecer(pedido, *, usuario, parecer: str):
    parecer = _exigir_texto(parecer, "parecer", "Obrigatório.")
    _mudar_status(
        pedido, Status.COM_PARECER, usuario, "parecer_emitido",
        parecer_articulador=parecer, parecer_por=usuario,
    )
    notifications_service.notificar_recurso_extra_com_parecer(
        pedido, notifications_service.usuarios_por_perfil("ugp"),
    )
    return pedido


@transaction.atomic
def devolver_pedido(pedido, *, usuario, justificativa: str):
    justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória para devolver o pedido.")
    _mudar_status(
        pedido, Status.DEVOLVIDA, usuario, "devolvido",
        parecer_articulador=justificativa, parecer_por=usuario,
    )
    notifications_service.notificar_recurso_extra_devolvido(pedido)
    return pedido


def _meta_do_pedido(pedido):
    if pedido.demanda_id and pedido.demanda_id.isdigit():
        demanda = Demand.objects.select_related("activity__acao__meta").filter(pk=int(pedido.demanda_id)).first()
        if demanda is not None:
            return demanda.meta
    if pedido.activity_id is not None:
        return pedido.activity.acao.meta
    return None


def _elevar_limite(pedido, valor: Decimal, usuario) -> None:
    limite = DemandIndividualLimit.objects.select_for_update().filter(
        solicitante=pedido.user, rubrica=pedido.rubrica,
    ).first()
    if limite is None:
        limite = DemandIndividualLimit.objects.create(
            solicitante=pedido.user, rubrica=pedido.rubrica, valor_limite=ZERO, criado_por=usuario,
        )
    antes = limite.valor_limite
    limite.valor_limite = antes + valor
    limite.save(update_fields=["valor_limite"])
    auditoria_service.registrar_evento(
        acao="aumento_limite", entidade=ENTIDADE_LIMITE, entidade_id=limite.pk, usuario=usuario,
        anteriores={"valor_limite": str(antes)},
        novos={
            "valor_limite": str(limite.valor_limite), "pedido": pedido.pk,
            "demanda": pedido.demanda_id, "rubrica": pedido.rubrica.slug,
        },
    )


def _conferir_pool(pedido, valor: Decimal, origem: BudgetAllocation | None, usuario):
    """(alerta, transferência). `alerta` é None quando não há como conferir o pool
    (pedido sem Meta, ou usuário sem território único)."""
    meta = _meta_do_pedido(pedido)
    if meta is None:
        return None, None
    try:
        nivel, sigla, territorio = budget_service.resolver_nivel_do_usuario(pedido.user)
    except PermissionDenied:
        return None, None
    check = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=pedido.rubrica.slug, nivel=nivel,
        estado_sigla=sigla, territorio=territorio, valor=valor,
    )
    if check.disponivel:
        return False, None
    if origem is None:
        return True, None

    if origem.nivel not in (budget_service.Nivel.ESTADUAL, budget_service.Nivel.NACIONAL):
        raise DRFValidationError({
            "origem_allocation": "O remanejamento só pode vir de saldo estadual ou nacional."
        })
    if check.allocation is None:
        raise DRFValidationError({"detail": "Nenhuma alocação territorial encontrada para receber o remanejamento."})

    destino = check.allocation
    faltante = valor - max(check.saldo, ZERO)
    origem = BudgetAllocation.objects.select_related("estado", "territorio").get(pk=origem.pk)
    origem_antes, destino_antes = _saldo(origem), _saldo(destino)
    motivo = f"Recurso extra #{pedido.pk}: {pedido.justificativa}"
    budget_service.remanejar(origem=origem, destino=destino, valor=faltante, usuario=usuario, justificativa=motivo)
    origem.refresh_from_db()
    destino.refresh_from_db()

    transferencia = BudgetTransfer.objects.create(
        tipo=BudgetTransfer.Tipo.ENTRE_NIVEIS, allocation_origem=origem, allocation_destino=destino,
        valor=faltante, motivo=motivo,
        saldo_origem_antes=origem_antes, saldo_origem_depois=_saldo(origem),
        saldo_destino_antes=destino_antes, saldo_destino_depois=_saldo(destino),
        aprovado_por=usuario, ip=get_audit_context()["ip"], increase_request=pedido,
    )
    auditoria_service.registrar_evento(
        acao="remanejamento.efetivado", entidade=ENTIDADE_REMANEJAMENTO, entidade_id=transferencia.pk,
        usuario=usuario,
        anteriores={"saldo_origem": str(origem_antes), "saldo_destino": str(destino_antes)},
        novos={
            "valor": str(faltante), "pedido": pedido.pk, "demanda": pedido.demanda_id,
            "origem": origem.pk, "destino": destino.pk,
            "saldo_origem": str(transferencia.saldo_origem_depois),
            "saldo_destino": str(transferencia.saldo_destino_depois),
        },
    )
    destinatarios = {
        u.pk: u for u in (
            *_destinatarios_saldo_territorial(
                nivel=origem.nivel, estado_sigla=origem.estado.sigla if origem.estado else None,
                territorio=origem.territorio,
            ),
            *_destinatarios_saldo_territorial(
                nivel=destino.nivel, estado_sigla=destino.estado.sigla if destino.estado else None,
                territorio=destino.territorio,
            ),
        )
    }
    notifications_service.notificar_remanejamento_efetivado(transferencia, list(destinatarios.values()))
    # O alerta some: o remanejamento já cobriu o que faltava no pool.
    return False, transferencia


@transaction.atomic
def decidir(pedido, *, usuario, decisao: str, valor_aprovado: Decimal | None = None,
            justificativa: str = "", origem_allocation: BudgetAllocation | None = None) -> dict:
    # Trava o pedido: duas decisões simultâneas não podem aprovar o mesmo pedido duas vezes.
    # `of=("self",)`: a Atividade é opcional (join externo), e o Postgres não aceita
    # FOR UPDATE no lado anulável de um join — só o pedido precisa ser travado.
    pedido = BudgetIncreaseRequest.objects.select_for_update(of=("self",)).select_related(
        "rubrica", "user", "activity__municipio__state", "activity__acao__meta",
    ).get(pk=pedido.pk)
    if decisao not in DECISOES:
        raise DRFValidationError({"decisao": f"Valor inválido. Esperado um de: {sorted(DECISOES)}."})
    destino_status = DECISOES[decisao]
    _exigir_transicao(pedido, destino_status)

    if decisao == "recusar":
        justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória para recusar o pedido.")
        valor_aprovado = None
    elif decisao == "aprovar_parcialmente":
        justificativa = _exigir_texto(
            justificativa, "justificativa", "Obrigatória para aprovar parcialmente o pedido.",
        )
        if valor_aprovado is None or not ZERO < valor_aprovado < pedido.valor_solicitado:
            raise DRFValidationError({
                "valor_aprovado": "Na aprovação parcial, informe um valor maior que zero e menor que o solicitado."
            })
    else:
        valor_aprovado = pedido.valor_solicitado
        justificativa = (justificativa or "").strip()

    alerta, transferencia = None, None
    if valor_aprovado is not None:
        alerta, transferencia = _conferir_pool(pedido, valor_aprovado, origem_allocation, usuario)
        _elevar_limite(pedido, valor_aprovado, usuario)

    _mudar_status(
        pedido, destino_status, usuario, f"decidido_{decisao}",
        valor_aprovado=valor_aprovado, justificativa_decisao=justificativa,
        decidido_por=usuario, decidido_em=timezone.now(),
    )
    notifications_service.notificar_recurso_extra_decidido(pedido)
    return {
        "pedido": pedido,
        "alerta_pool_insuficiente": alerta,
        "transferencia": transferencia,
    }
