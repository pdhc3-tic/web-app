"""Solicitação de Recurso Extra (SGP §6.6) e o remanejamento que a decisão da UGP pode disparar.

O pedido percorre a máquina de estados de `BudgetIncreaseRequest`. Aprovar eleva o
limite individual do solicitante na rubrica e só se conclui com o pool territorial
cobrindo o que a demanda precisa reservar: se faltar saldo, a UGP informa uma
alocação estadual ou nacional e o remanejamento acontece na própria decisão. A
demanda bloqueada não é submetida sozinha: o limite maior só a deixa passar nas
duas travas quando o solicitante submeter de novo.

Ordem de lock: pedido → `DemandIndividualLimit` → `BudgetAllocation` (em ordem de pk)
→ `Demand` → `DemandRequest` da demanda, a ordem de `backend/docs/orcamento.md`.
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
from apps.sgd.services import balance as balance_service
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


def _travar_pedido(pedido) -> BudgetIncreaseRequest:
    """Relê o pedido travado: duas ações simultâneas sobre ele (parecer e devolução, duas
    decisões) não podem partir do mesmo status nem gravar uma por cima da outra.
    `of=("self",)`: a Atividade é opcional (join externo), e o Postgres não aceita FOR
    UPDATE no lado anulável de um join."""
    return BudgetIncreaseRequest.objects.select_for_update(of=("self",)).select_related(
        "rubrica", "user", "activity__municipio__state", "activity__acao__meta",
    ).get(pk=pedido.pk)


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


def _demanda_do_pedido(pedido, *, travar: bool = False) -> Demand | None:
    if not (pedido.demanda_id and pedido.demanda_id.isdigit()):
        return None
    demandas = Demand.objects.select_related("activity__acao__meta")
    if travar:
        # Só a Demand: Atividade, Ação e Meta vêm no join, mas ninguém as disputa aqui.
        demandas = demandas.select_for_update(of=("self",))
    return demandas.filter(pk=int(pedido.demanda_id)).first()


def _necessario(solicitacoes) -> Decimal:
    """O que a próxima submissão vai reservar na rubrica: as solicitações que ainda
    não têm reserva ativa."""
    return sum((s.valor_estimado for s in solicitacoes if not balance_service.reserva_ativa(s)), ZERO)


def _deficit_individual(demanda: Demand, rubrica) -> Decimal:
    limite = DemandIndividualLimit.objects.filter(solicitante=demanda.solicitante, rubrica=rubrica).first()
    # Sem truncar em zero: o saldo fica negativo depois de um excedente autorizado
    # (`ignorar_limite_individual`), e o aumento precisa cobrir isso também.
    saldo = limite.saldo_disponivel if limite else ZERO
    return _necessario(demanda.solicitacoes.filter(rubrica=rubrica)) - saldo


def _exigir_valor_cobre_o_deficit(demanda: Demand, rubrica, valor: Decimal) -> None:
    deficit = _deficit_individual(demanda, rubrica)
    if deficit <= ZERO:
        raise DRFValidationError({
            "demanda": "A demanda não está bloqueada pelo limite individual nesta rubrica."
        })
    # SGP §6.6 deixa o valor livre para ajuste na devolução; o piso é o "valor faltante" do
    # SGD §4.1, e a UGP pode conceder menos (aprovação parcial).
    if valor < deficit:
        raise DRFValidationError({
            "valor_solicitado": f"Não pode ser menor que o valor que falta no limite individual: R$ {deficit}."
        })


@transaction.atomic
def criar(*, demanda: Demand, rubrica, justificativa: str, usuario, valor_solicitado: Decimal | None = None,
          periodo_aplicacao: str = "", submeter: bool = True) -> BudgetIncreaseRequest:
    # Serializa pedidos concorrentes da mesma demanda: o de baixo vê o do de cima.
    demanda = Demand.objects.select_for_update().select_related("solicitante").get(pk=demanda.pk)
    if demanda.status not in STATUS_EDITAVEIS:
        raise DRFValidationError({
            "demanda": "Só uma demanda em Rascunho ou Devolvida, a que o bloqueio impede de submeter, "
                       "pode pedir recurso extra."
        })
    if not demanda.solicitacoes.filter(rubrica=rubrica).exists():
        raise DRFValidationError({"rubrica": "A demanda não tem solicitação nesta rubrica."})
    justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória.")
    if valor_solicitado is not None:
        _exigir_valor_positivo(valor_solicitado)
    if BudgetIncreaseRequest.objects.filter(
        demanda_id=str(demanda.pk), rubrica=rubrica,
    ).exclude(status__in=BudgetIncreaseRequest.TERMINAIS).exists():
        raise DRFValidationError({"demanda": "Já existe um pedido de recurso extra em andamento nesta rubrica."})
    deficit = _deficit_individual(demanda, rubrica)
    if valor_solicitado is None:
        valor_solicitado = deficit
    _exigir_valor_cobre_o_deficit(demanda, rubrica, valor_solicitado)

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
        pedido = submeter_pedido(pedido, usuario=usuario)
    return pedido


@transaction.atomic
def editar(pedido, *, usuario, valor_solicitado=None, justificativa=None, periodo_aplicacao=None):
    pedido = _travar_pedido(pedido)
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
        demanda = _demanda_do_pedido(pedido)
        if demanda is not None:
            _exigir_valor_cobre_o_deficit(demanda, pedido.rubrica, valor_solicitado)
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
    pedido = _travar_pedido(pedido)
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
    pedido = _travar_pedido(pedido)
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
    pedido = _travar_pedido(pedido)
    _mudar_status(
        pedido, Status.DEVOLVIDA, usuario, "devolvido",
        parecer_articulador=justificativa, parecer_por=usuario,
    )
    notifications_service.notificar_recurso_extra_devolvido(pedido)
    return pedido


def _meta_do_pedido(pedido):
    demanda = _demanda_do_pedido(pedido)
    if demanda is not None:
        return demanda.meta
    if pedido.activity_id is not None:
        return pedido.activity.acao.meta
    return None


def _travar_limite(pedido, usuario) -> DemandIndividualLimit:
    # Sem limite, o FOR UPDATE não trava nada e duas decisões do mesmo solicitante e
    # rubrica tentam criá-lo. O `get_or_create` cria num savepoint: a segunda espera a
    # primeira no índice único e, no IntegrityError, relê a linha travada e já elevada.
    limite, _ = DemandIndividualLimit.objects.select_for_update().get_or_create(
        solicitante=pedido.user, rubrica=pedido.rubrica,
        defaults={"valor_limite": ZERO, "criado_por": usuario},
    )
    return limite


def _elevar_limite(pedido, limite: DemandIndividualLimit, valor: Decimal, usuario) -> None:
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


def _travar_alocacoes(pedido, origem: BudgetAllocation | None):
    """Trava a alocação territorial do solicitante e, se houver, a de origem do
    remanejamento, em ordem crescente de pk, como `remanejar`. Devolve (destino, origem)."""
    meta = _meta_do_pedido(pedido)
    if meta is None:
        raise DRFValidationError({"detail": "Pedido sem Meta: não há como conferir o pool territorial."})
    try:
        nivel, sigla, territorio = budget_service.resolver_nivel_do_usuario(pedido.user)
    except PermissionDenied as exc:
        raise DRFValidationError({
            "detail": f"Não há como conferir o pool territorial do solicitante. {exc.detail}"
        }) from exc
    # Só localiza a alocação: o saldo é lido depois, com ela travada.
    check = budget_service.saldo_para_consulta(
        meta_id=meta.pk, rubrica_slug=pedido.rubrica.slug, nivel=nivel,
        estado_sigla=sigla, territorio=territorio, valor=ZERO,
    )
    if check.allocation is None:
        raise DRFValidationError({"detail": "Nenhuma alocação territorial encontrada para o solicitante nesta rubrica."})
    if origem is not None and origem.nivel not in (budget_service.Nivel.ESTADUAL, budget_service.Nivel.NACIONAL):
        raise DRFValidationError({
            "origem_allocation": "O remanejamento só pode vir de saldo estadual ou nacional."
        })

    pks = {check.allocation.pk} | ({origem.pk} if origem is not None else set())
    travadas = {
        pk: BudgetAllocation.objects.select_for_update(of=("self",)).select_related("estado", "territorio").get(pk=pk)
        for pk in sorted(pks)
    }
    return travadas[check.allocation.pk], (travadas[origem.pk] if origem is not None else None)


def _cobrir_pool(pedido, necessario: Decimal, destino: BudgetAllocation, origem: BudgetAllocation | None,
                 usuario) -> BudgetTransfer | None:
    """Garante que o pool territorial, já travado, cobre o que a demanda precisa reservar.
    Sem cobrir, só passa com `origem`, que remaneja a diferença."""
    faltante = necessario - _saldo(destino)
    if faltante <= ZERO:
        return None
    if origem is None:
        raise DRFValidationError({
            "origem_allocation": (
                f"O pool territorial não cobre os R$ {necessario} que a demanda precisa reservar "
                f"(R$ {_saldo(destino)} disponível). Informe a alocação estadual ou nacional "
                "que cobre a diferença."
            )
        })
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
    return transferencia


def _exigir_demanda_editavel(demanda: Demand) -> None:
    if demanda.status not in STATUS_EDITAVEIS:
        raise DRFValidationError({
            "demanda": (
                f"A demanda está '{demanda.get_status_display()}': só em Rascunho ou Devolvida o "
                "pedido ainda tem bloqueio a liberar. Recuse o pedido."
            )
        })


@transaction.atomic
def decidir(pedido, *, usuario, decisao: str, valor_aprovado: Decimal | None = None,
            justificativa: str = "", origem_allocation: BudgetAllocation | None = None) -> dict:
    pedido = _travar_pedido(pedido)
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
        justificativa = _exigir_texto(justificativa, "justificativa", "Obrigatória para aprovar o pedido.")

    transferencia = None
    if valor_aprovado is not None:
        limite = _travar_limite(pedido, usuario)
        demanda = _demanda_do_pedido(pedido)
        if demanda is not None:
            # Fora de Rascunho/Devolvida, o Arlo e a autorização travam a Demand ou a
            # solicitação antes do limite: checar antes de travar evita o deadlock.
            _exigir_demanda_editavel(demanda)
        destino, origem = _travar_alocacoes(pedido, origem_allocation)
        if demanda is None:
            necessario = valor_aprovado
        else:
            # A Demand depois das alocações, como a submissão e os cancelamentos, que só a
            # atualizam depois de mexer no saldo. A segunda checagem pega a demanda
            # submetida enquanto a decisão esperava o lock.
            demanda = _demanda_do_pedido(pedido, travar=True)
            _exigir_demanda_editavel(demanda)
            # Todas as solicitações da demanda, não só as da rubrica: uma de outra rubrica
            # pode ser editada para esta. `order_by("pk")` tira o join com Demand.
            solicitacoes = [
                s for s in demanda.solicitacoes.select_for_update().order_by("pk")
                if s.rubrica_id == pedido.rubrica_id
            ]
            necessario = _necessario(solicitacoes)
            deficit = necessario - limite.saldo_disponivel
            if decisao == "aprovar" and valor_aprovado < deficit:
                raise DRFValidationError({
                    "valor_aprovado": (
                        f"A demanda precisa agora de R$ {deficit} a mais no limite individual, acima dos "
                        f"R$ {valor_aprovado} solicitados: a demanda ou o limite mudou desde o pedido. "
                        "Recuse para que o solicitante abra um novo pedido com o valor atual."
                    )
                })
        _elevar_limite(pedido, limite, valor_aprovado, usuario)
        transferencia = _cobrir_pool(pedido, necessario, destino, origem, usuario)

    _mudar_status(
        pedido, destino_status, usuario, f"decidido_{decisao}",
        valor_aprovado=valor_aprovado, justificativa_decisao=justificativa,
        decidido_por=usuario, decidido_em=timezone.now(),
    )
    notifications_service.notificar_recurso_extra_decidido(pedido)
    return {"pedido": pedido, "transferencia": transferencia}
