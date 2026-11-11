from __future__ import annotations

from django.db import transaction

from apps.sgd.exceptions import JustificativaObrigatoria, RegraDeNegocio
from apps.sgd.models.demand import STATUS_EDITAVEIS, Demand
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import anexos as anexos_service
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import contexto
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.demand_request import (
    _exigir_minimo_cotacoes_equipamento,  # noqa: F401
    exigir_regras_de_submissao,
    rubrica_para_tipo,
    validar_campos_json,
)
from apps.sgp.models import Activity
from apps.sgp.services.activity import criar_planejada
from apps.sgp.services.activity_status import ActivityRuleError

ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA = {"cancelada", "nao_realizada"}
ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA = {"em_andamento", "concluido", "concluido_sem_evidencia"}
# Oferecidas na busca do formulário. As demais que aceitam demanda pedem justificativa
# de despesa posterior e continuam valendo pelo `activity_id`.
ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA = ("planejado", "agendado")
# Campo do cadastro da atividade → campo que o cliente envia na criação inline.
_CAMPO_DA_ATIVIDADE_INLINE = {
    "titulo": "activity_titulo",
    "tipo_atividade": "activity_tipo_atividade",
    "acao": "activity_acao_id",
    "municipio": "activity_municipio_id",
    "data_inicio": "activity_data_prevista",
    "data_fim": "activity_data_prevista",
}


def _despesa_posterior_e_valida(activity) -> bool:
    if activity.status in ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA:
        raise RegraDeNegocio(
            f"Atividade em status '{activity.get_status_display()}' não aceita novas demandas.", campo="activity",
        )
    return activity.status in ACTIVITY_STATUS_EXIGEM_JUSTIFICATIVA


def atividades_elegiveis(*, q: str = "", status=()):
    """Atividades que o solicitante pode vincular, de qualquer estado ou território: a
    abrangência da demanda vem de quem a cria, não da atividade."""
    status_pedidos = set(status)
    invalidos = status_pedidos - set(ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA)
    if invalidos:
        raise RegraDeNegocio(
            f"Valor inválido. Esperado um de: {list(ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA)}.", campo="status",
        )
    qs = Activity.objects.filter(
        ativo=True, status__in=status_pedidos or ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA,
    ).select_related("municipio__state", "tecnico_responsavel")
    if q := q.strip():
        qs = qs.filter(titulo__icontains=q)
    return qs.order_by("data_inicio", "pk")


def criar_activity_inline(*, titulo, tipo_atividade, acao, municipio, data_prevista, usuario):
    try:
        return criar_planejada(
            titulo=titulo, tipo_atividade=tipo_atividade, acao=acao, municipio=municipio,
            data_prevista=data_prevista, usuario=usuario,
        )
    except ActivityRuleError as exc:
        raise RegraDeNegocio(exc.message, campo=_CAMPO_DA_ATIVIDADE_INLINE.get(exc.field, "activity")) from exc


@transaction.atomic
def criar_demanda(*, titulo, activity, justificativa, solicitante) -> Demand:
    despesa_posterior = _despesa_posterior_e_valida(activity)
    if despesa_posterior and not justificativa:
        raise JustificativaObrigatoria("Obrigatória para demandas de atividades já em andamento/concluídas.")
    # Território do solicitante, congelado aqui: a atividade pode estar em
    # outro estado, e a lotação do usuário pode mudar depois.
    estado_sigla, territorio = contexto.abrangencia_para_nova_demanda(solicitante=solicitante)
    demand = Demand.objects.create(
        titulo=titulo, activity=activity, justificativa=justificativa,
        solicitante=solicitante, despesa_posterior=despesa_posterior,
        estado_sigla=estado_sigla, territorio=territorio,
    )
    auditoria_service.registrar_status(demand, de=None, para=demand.status, usuario=solicitante)
    return demand


def _exigir_editavel(demand) -> None:
    if demand.status not in STATUS_EDITAVEIS:
        raise RegraDeNegocio(
            f"Demanda em status '{demand.get_status_display()}' não pode ser editada.", campo="status",
        )


def _travar_editavel(demand) -> None:
    """Trava a `Demand` e confere o status na linha travada: quem segurava o lock
    pode ter submetido ou cancelado a demanda. Vem depois do saldo e antes de gravar
    a solicitação, na ordem de lock de `backend/docs/orcamento.md`; a submissão,
    que reservou o saldo antes, confere sob o mesmo lock que as solicitações não
    mudaram."""
    demand.status = workflow_service.travar_e_ler_status(demand)
    _exigir_editavel(demand)


@transaction.atomic
def atualizar_demanda(demand, *, titulo=None, justificativa=None) -> Demand:
    _travar_editavel(demand)
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
    # DEFERRABLE INITIALLY DEFERRED e só é conferida no commit.
    _travar_editavel(demand)

    validado = validar_campos_json(tipo, campos_json, demand.activity)
    rubrica = rubrica_para_tipo(tipo)

    valor_final = validado.valor_estimado_auto if validado.valor_estimado_auto is not None else valor_estimado
    if valor_final is None:
        raise RegraDeNegocio("Obrigatório para este tipo de solicitação.", campo="valor_estimado")
    if valor_final <= 0:
        raise RegraDeNegocio("Deve ser maior que zero.", campo="valor_estimado")

    solicitacao = DemandRequest.objects.create(
        demanda=demand, tipo_id=tipo, rubrica=rubrica, campos_json=validado.campos_json,
        beneficiario_cpf=validado.beneficiario_cpf, valor_estimado=valor_final, ordem=ordem,
    )
    anexos_service.vincular_anexos(solicitacao)
    demand.recalcular_totais()
    return solicitacao


@transaction.atomic
def atualizar_solicitacao(solicitacao, *, usuario, tipo=None, campos_json=None, valor_estimado=None):
    """RF07 — editar uma solicitação de uma demanda em Rascunho/Devolvida,
    sem precisar remover e recriar.

    Em Devolvida a reserva de saldo é mantida (§4.2) — se a solicitação já
    tem reserva ativa e o valor muda, ajusta a reserva existente em vez de
    só trocar o campo; a resubmissão não pede saldo adicional pra ela."""
    demand = solicitacao.demanda
    _exigir_editavel(demand)
    # Com o limite travado: a reserva lida decide se há ajuste e é gravada abaixo.
    balance_service.reler_reserva_travada(solicitacao)

    tipo_final = tipo or solicitacao.tipo_id
    campos_final = campos_json if campos_json is not None else solicitacao.campos_json
    # Mesmo tipo: o validador pode preservar o que foi calculado na gravação (ex.: diária).
    anteriores = solicitacao.campos_json if tipo_final == solicitacao.tipo_id else None
    validado = validar_campos_json(tipo_final, campos_final, demand.activity, anteriores=anteriores)
    # Não retroativo: só consulta o catálogo se o tipo mudou.
    rubrica = rubrica_para_tipo(tipo_final) if tipo_final != solicitacao.tipo_id else solicitacao.rubrica

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
        balance_service.ajustar_duas_travas(
            demand_request=solicitacao, novo_valor=valor_final, usuario=usuario, adiar_gravacao=True,
        )
    _travar_editavel(demand)

    solicitacao.tipo_id = tipo_final
    solicitacao.rubrica = rubrica
    solicitacao.campos_json = validado.campos_json
    solicitacao.beneficiario_cpf = validado.beneficiario_cpf
    solicitacao.valor_estimado = valor_final
    solicitacao.save(update_fields=[
        "tipo", "rubrica", "campos_json", "beneficiario_cpf", "valor_estimado", "valor_reservado",
        "valor_excedente", "atualizado_em",
    ])
    anexos_service.vincular_anexos(solicitacao)
    demand.recalcular_totais()
    return solicitacao


@transaction.atomic
def remover_solicitacao(solicitacao, *, usuario) -> None:
    _exigir_editavel(solicitacao.demanda)
    balance_service.reler_reserva(solicitacao)
    if solicitacao.reserva_ativa:
        balance_service.liberar_duas_travas(
            demand_request=solicitacao, usuario=usuario,
            motivo="Solicitação removida durante edição da demanda.", adiar_gravacao=True,
        )
    _travar_editavel(solicitacao.demanda)
    solicitacao.delete()
    solicitacao.demanda.recalcular_totais()


def submeter_demanda(demand, *, usuario) -> Demand:
    exigir_regras_de_submissao(demand)
    return workflow_service.executar_transicao(demand, "submetida", ator=usuario)


def cancelar_demanda(demand, *, usuario, motivo: str = "") -> Demand:
    return workflow_service.executar_transicao(demand, "cancelada", ator=usuario, justificativa=motivo)
