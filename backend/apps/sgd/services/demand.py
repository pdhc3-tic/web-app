from __future__ import annotations

from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.models.demand import STATUS_EDITAVEIS, Demand
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.approval import pode_cancelar, transition, usuarios_articuladores_do_estado
from apps.sgd.services.demand_request import rubrica_slug_para_tipo, validar_campos_json
from apps.sgp.models import BudgetRubrica

ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA = {"cancelada", "nao_realizada"}
ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA = {"em_andamento", "concluido", "concluido_sem_evidencia"}


def _despesa_posterior_e_valida(activity) -> bool:
    if activity.status in ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA:
        raise DRFValidationError({
            "activity": f"Atividade em status '{activity.get_status_display()}' não aceita novas demandas."
        })
    return activity.status in ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA


@transaction.atomic
def criar_activity_inline(*, titulo, tipo_atividade, acao, municipio, data_prevista, usuario):
    # Activity tem outros campos NOT NULL sem default (técnico, forma de
    # atuação, âmbito, data_fim, descrição narrativa) que este formulário
    # mínimo não coleta — preenchidos com um valor editável depois.
    from apps.sgp.models import Activity

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
        raise DRFValidationError({
            "justificativa": "Obrigatória para demandas de atividades já em andamento/concluídas (§2.3)."
        })
    return Demand.objects.create(
        titulo=titulo, activity=activity, justificativa=justificativa,
        solicitante=solicitante, despesa_posterior=despesa_posterior,
    )


def _exigir_editavel(demand) -> None:
    if demand.status not in STATUS_EDITAVEIS:
        raise DRFValidationError({
            "status": f"Demanda em status '{demand.get_status_display()}' não pode ser editada (RF07)."
        })


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
    _exigir_editavel(demand)
    from apps.sgd.models.demand_request import DemandRequest

    validado = validar_campos_json(tipo, campos_json, demand.activity)
    rubrica = BudgetRubrica.objects.get(slug=rubrica_slug_para_tipo(tipo))

    valor_final = validado.valor_estimado_auto if validado.valor_estimado_auto is not None else valor_estimado
    if valor_final is None:
        raise DRFValidationError({"valor_estimado": "Obrigatório para este tipo de solicitação."})

    return DemandRequest.objects.create(
        demanda=demand, tipo=tipo, rubrica=rubrica, campos_json=validado.campos_json,
        beneficiario_cpf=validado.beneficiario_cpf, valor_estimado=valor_final, ordem=ordem,
    )


def _exigir_minimo_cotacoes_equipamento(demand) -> None:
    from apps.sgd.models.demand_document import DemandDocument

    if not demand.solicitacoes.filter(tipo="equipamento").exists():
        return
    cotacoes = DemandDocument.objects.filter(demanda=demand, tipo="cotacao", ativo=True).count()
    if cotacoes < 3:
        raise DRFValidationError({
            "documentos": "Solicitação de Aquisição de Equipamentos exige no mínimo 3 cotações em PDF (§3.6)."
        })


@transaction.atomic
def submeter_demanda(demand, *, usuario) -> Demand:
    # Tudo-ou-nada: verifica as duas travas de todas as solicitações antes
    # de reservar qualquer uma.
    _exigir_minimo_cotacoes_equipamento(demand)

    solicitacoes = list(demand.solicitacoes.select_related("rubrica").all())
    if not solicitacoes:
        raise DRFValidationError({"solicitacoes": "A demanda precisa ter ao menos uma solicitação de recurso."})

    meta = demand.activity.acao.meta
    bloqueios = {}
    for solicitacao in solicitacoes:
        check = balance_service.verificar_duas_travas(
            solicitante=demand.solicitante, rubrica=solicitacao.rubrica, meta=meta,
            valor=solicitacao.valor_estimado,
        )
        if not check.disponivel:
            trava = check.trava_bloqueada
            motivo = (check.individual if trava == "individual" else check.territorial).motivo_bloqueio
            bloqueios[str(solicitacao.pk)] = {"trava": trava, "motivo": motivo}
    if bloqueios:
        raise DRFValidationError({"solicitacoes_bloqueadas": bloqueios})

    for solicitacao in solicitacoes:
        balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=usuario)

    transition(demand, "submetida")
    demand.save(update_fields=["status", "atualizado_em"])

    sigla = demand.activity.municipio.state.sigla
    notifications_service.notificar_submissao(demand, usuarios_articuladores_do_estado(sigla))
    return demand


@transaction.atomic
def cancelar_demanda(demand, *, usuario, motivo: str = "") -> Demand:
    if not pode_cancelar(demand, usuario):
        raise DRFValidationError({"status": "Você não pode cancelar esta demanda neste status (RF09)."})

    for solicitacao in demand.solicitacoes.all():
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=usuario,
            motivo=motivo or "Cancelada pelo solicitante.",
        )

    demand.status = "cancelada"
    demand.save(update_fields=["status", "atualizado_em"])
    return demand
