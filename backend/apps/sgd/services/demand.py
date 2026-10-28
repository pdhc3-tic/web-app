from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.sgd.exceptions import JustificativaObrigatoria, RegraDeNegocio, SaldoInsuficiente, TransicaoInvalida
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.demand import STATUS_EDITAVEIS, Demand
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.approval import aplicar_transicao, marcar_cancelada, pode_cancelar, pode_cancelar_autorizada
from apps.sgd.services.demand_request import rubrica_para_tipo, validar_campos_json
from apps.sgp.models import Activity

ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA = {"cancelada", "nao_realizada"}
ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA = {"em_andamento", "concluido", "concluido_sem_evidencia"}


def _despesa_posterior_e_valida(activity) -> bool:
    if activity.status in ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA:
        raise RegraDeNegocio(
            f"Atividade em status '{activity.get_status_display()}' não aceita novas demandas.", campo="activity",
        )
    return activity.status in ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA


@transaction.atomic
def criar_activity_inline(*, titulo, tipo_atividade, acao, municipio, data_prevista, usuario):
    # Activity tem outros campos NOT NULL sem default (técnico, forma de
    # atuação, âmbito, data_fim, descrição narrativa) que este formulário
    # mínimo não coleta — preenchidos com um valor editável depois.
    return Activity.objects.create(
        titulo=titulo, tipo_atividade=tipo_atividade, acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="municipal",
        tecnico_responsavel=usuario, data_inicio=data_prevista, data_fim=data_prevista,
        descricao_narrativa=f"Atividade criada a partir da demanda '{titulo}'.",
        status="planejado", criado_por=usuario,
    )


@transaction.atomic
def criar_demanda(*, titulo, activity, justificativa, solicitante) -> Demand:
    despesa_posterior = _despesa_posterior_e_valida(activity)
    if despesa_posterior and not justificativa:
        raise JustificativaObrigatoria("Obrigatória para demandas de atividades já em andamento/concluídas.")
    demand = Demand.objects.create(
        titulo=titulo, activity=activity, justificativa=justificativa,
        solicitante=solicitante, despesa_posterior=despesa_posterior,
    )
    auditoria_service.registrar_status(demand, de=None, para=demand.status, usuario=solicitante)
    return demand


def _exigir_editavel(demand) -> None:
    if demand.status not in STATUS_EDITAVEIS:
        raise RegraDeNegocio(
            f"Demanda em status '{demand.get_status_display()}' não pode ser editada.", campo="status",
        )


@transaction.atomic
def atualizar_demanda(demand, *, titulo=None, justificativa=None) -> Demand:
    _exigir_editavel(demand)
    campos_alterados = ["atualizado_em"]
    if titulo is not None:
        demand.titulo = titulo
        campos_alterados.append("titulo")
    if justificativa is not None:
        demand.justificativa = justificativa
        campos_alterados.append("justificativa")
    demand.save(update_fields=campos_alterados)
    return demand


@transaction.atomic
def adicionar_solicitacao(demand, *, tipo, campos_json, valor_estimado=None, ordem=0):
    # A decisão do recurso extra trava a Demand para recalcular o déficit sobre as
    # solicitações; a inclusão disputa o mesmo lock. A FK não basta: no Postgres ela é
    # DEFERRABLE INITIALLY DEFERRED e só é conferida no commit. O status vem da linha
    # travada: quem segurava o lock pode ter submetido ou cancelado a demanda.
    demand.status = Demand.objects.select_for_update().values_list("status", flat=True).get(pk=demand.pk)
    _exigir_editavel(demand)

    validado = validar_campos_json(tipo, campos_json, demand.activity)
    rubrica = rubrica_para_tipo(tipo)

    valor_final = validado.valor_estimado_auto if validado.valor_estimado_auto is not None else valor_estimado
    if valor_final is None:
        raise RegraDeNegocio("Obrigatório para este tipo de solicitação.", campo="valor_estimado")
    if valor_final <= 0:
        raise RegraDeNegocio("Deve ser maior que zero.", campo="valor_estimado")

    return DemandRequest.objects.create(
        demanda=demand, tipo=tipo, rubrica=rubrica, campos_json=validado.campos_json,
        beneficiario_cpf=validado.beneficiario_cpf, valor_estimado=valor_final, ordem=ordem,
    )


@transaction.atomic
def atualizar_solicitacao(solicitacao, *, usuario, tipo=None, campos_json=None, valor_estimado=None):
    """RF07 — editar uma solicitação de uma demanda em Rascunho/Devolvida,
    sem precisar remover e recriar.

    Em Devolvida a reserva de saldo é mantida (§4.2) — se a solicitação já
    tem reserva ativa e o valor muda, ajusta a reserva existente em vez de
    só trocar o campo; a resubmissão não pede saldo adicional pra ela."""
    demand = solicitacao.demanda
    _exigir_editavel(demand)
    balance_service.reler_reserva(solicitacao)

    tipo_final = tipo or solicitacao.tipo
    campos_final = campos_json if campos_json is not None else solicitacao.campos_json
    validado = validar_campos_json(tipo_final, campos_final, demand.activity)
    # Não retroativo: só consulta o mapeamento vigente se o tipo mudou.
    rubrica = rubrica_para_tipo(tipo_final) if tipo_final != solicitacao.tipo else solicitacao.rubrica

    valor_final = validado.valor_estimado_auto
    if valor_final is None:
        valor_final = valor_estimado if valor_estimado is not None else solicitacao.valor_estimado
    if valor_final <= 0:
        raise RegraDeNegocio("Deve ser maior que zero.", campo="valor_estimado")

    tem_reserva = solicitacao.reserva_ativa
    if tem_reserva and rubrica.pk != solicitacao.rubrica_id:
        raise RegraDeNegocio(
            "Não é possível trocar o tipo de uma solicitação com reserva de saldo ativa "
            "(mudaria a rubrica). Remova e crie uma nova solicitação.",
            campo="tipo",
        )
    if tem_reserva and valor_final != solicitacao.valor_reservado:
        balance_service.ajustar_duas_travas(demand_request=solicitacao, novo_valor=valor_final, usuario=usuario)

    solicitacao.tipo = tipo_final
    solicitacao.rubrica = rubrica
    solicitacao.campos_json = validado.campos_json
    solicitacao.beneficiario_cpf = validado.beneficiario_cpf
    solicitacao.valor_estimado = valor_final
    solicitacao.save(update_fields=[
        "tipo", "rubrica", "campos_json", "beneficiario_cpf", "valor_estimado", "atualizado_em",
    ])
    return solicitacao


@transaction.atomic
def remover_solicitacao(solicitacao, *, usuario) -> None:
    _exigir_editavel(solicitacao.demanda)
    balance_service.reler_reserva(solicitacao)
    if solicitacao.reserva_ativa:
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=usuario,
            motivo="Solicitação removida durante edição da demanda.",
        )
    solicitacao.delete()


def _exigir_minimo_cotacoes_equipamento(demand) -> None:
    if not demand.solicitacoes.filter(tipo="equipamento").exists():
        return
    fornecedores = list(
        DemandDocument.objects.filter(demanda=demand, tipo="cotacao", ativo=True)
        .values_list("fornecedor", flat=True)
    )
    if len(fornecedores) < 3:
        raise RegraDeNegocio(
            "Solicitação de Aquisição de Equipamentos exige no mínimo 3 cotações em PDF.", campo="documentos",
        )
    if len(set(fornecedores)) < len(fornecedores):
        raise RegraDeNegocio("As cotações precisam ser de fornecedores distintos.", campo="documentos")


@transaction.atomic
def submeter_demanda(demand, *, usuario) -> Demand:
    # Tudo-ou-nada: verifica as duas travas de todas as solicitações antes
    # de reservar qualquer uma.
    _exigir_minimo_cotacoes_equipamento(demand)

    # Ordenadas por rubrica: solicitações de demandas concorrentes sempre
    # travam BudgetAllocation na mesma ordem, evitando deadlock.
    solicitacoes = list(demand.solicitacoes.select_related("rubrica").order_by("rubrica_id", "pk").all())
    if not solicitacoes:
        raise RegraDeNegocio("A demanda precisa ter ao menos uma solicitação de recurso.", campo="solicitacoes")

    bloqueios = {}
    # Solicitações da mesma rubrica disputam o mesmo limite e a mesma
    # alocação: cada uma é conferida contra o saldo que sobra depois das
    # anteriores que passaram. As barradas não consomem — senão uma menor,
    # que ainda cabe, seria barrada por causa de uma maior que não coube.
    consumo_por_rubrica: dict[int, Decimal] = {}
    for solicitacao in solicitacoes:
        # Com reserva já ativa (ex.: ressubmissão de Devolvida sem edição
        # nessa solicitação específica), o saldo já desconta essa reserva —
        # checar o valor cheio de novo bloquearia à toa.
        if solicitacao.reserva_ativa:
            continue
        consumo_previo = consumo_por_rubrica.get(solicitacao.rubrica_id, balance_service.ZERO)
        check = balance_service.verificar_duas_travas(
            solicitante=demand.solicitante, rubrica=solicitacao.rubrica, valor=solicitacao.valor_estimado,
            demand_request=solicitacao, consumo_previo=consumo_previo,
        )
        if not check.disponivel:
            bloqueios[solicitacao.pk] = check.bloqueio(solicitacao_id=solicitacao.pk)
        else:
            consumo_por_rubrica[solicitacao.rubrica_id] = consumo_previo + solicitacao.valor_estimado
    if bloqueios:
        raise SaldoInsuficiente.para_submissao(bloqueios)

    for solicitacao in solicitacoes:
        balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=usuario, adiar_gravacao=True)

    aplicar_transicao(demand, "submetida", usuario=usuario)
    balance_service.gravar_estado_da_reserva(solicitacoes)

    sigla = demand.activity.municipio.state.sigla
    notifications_service.notificar_submissao(demand, notifications_service.usuarios_articuladores_do_estado(sigla))
    return demand


@transaction.atomic
def cancelar_demanda(demand, *, usuario, motivo: str = "") -> Demand:
    estava_autorizada = demand.status == "autorizada"
    if estava_autorizada:
        if not pode_cancelar_autorizada(usuario):
            raise PermissionDenied("Seu perfil não pode cancelar uma demanda autorizada.")
        if not motivo.strip():
            raise JustificativaObrigatoria("Obrigatória para cancelar uma demanda autorizada.")
    elif not pode_cancelar(demand, usuario):
        raise TransicaoInvalida("Você não pode cancelar esta demanda neste status.")

    solicitacoes = list(demand.solicitacoes.order_by("rubrica_id", "pk"))
    for solicitacao in solicitacoes:
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=usuario,
            motivo=motivo or "Cancelada pelo solicitante.", adiar_gravacao=True,
        )

    # Dois cancelamentos simultâneos passam pela checagem acima com o mesmo status;
    # só o primeiro o encontra ao travar a linha. O lock vem depois das reservas,
    # na ordem da submissão (limite → alocação → Demand).
    status_atual = Demand.objects.select_for_update().values_list("status", flat=True).get(pk=demand.pk)
    if status_atual != demand.status:
        raise TransicaoInvalida("A demanda mudou de status durante o cancelamento. Recarregue e tente de novo.")

    marcar_cancelada(demand, usuario=usuario)
    balance_service.gravar_estado_da_reserva(solicitacoes)
    if estava_autorizada:
        ApprovalStep.objects.create(
            demanda=demand, etapa="cancelamento", responsavel=usuario,
            acao="cancelado", justificativa=motivo,
        )
    return demand
