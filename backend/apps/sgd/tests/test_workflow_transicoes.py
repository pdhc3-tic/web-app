"""A tabela `TRANSICOES` contra as tabelas de estados, de efeito no saldo e de
notificações do documento de requisitos do SGD, transcritas aqui."""
from decimal import Decimal

import pytest

from apps.sgd.exceptions import JustificativaObrigatoria, TransicaoInvalida
from apps.sgd.models.demand import Demand
from apps.sgd.services import balance as balance_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.workflow import (
    AJUSTAR,
    EXECUTAR,
    LIBERAR,
    MANTER,
    ORIGEM_ARLO,
    ORIGEM_SISTEMA,
    ORIGEM_USUARIO,
    RESERVAR,
    SOLICITANTE,
    TRANSICOES,
    buscar_transicao,
)
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db

# Estados e transições: (de, para) → quem age.
ESTADOS = {
    ("rascunho", "submetida"): SOLICITANTE,
    ("submetida", "pre_autorizada"): "articulador-estadual",
    ("submetida", "devolvida"): "articulador-estadual",
    ("devolvida", "submetida"): SOLICITANTE,
    ("pre_autorizada", "autorizada"): "ugp",
    ("pre_autorizada", "recusada"): "ugp",
    ("autorizada", "em_atendimento"): "fgd",
    ("em_atendimento", "concluida"): "fgd",
}

# "Cancelada pelo solicitante antes da autorização, ou automaticamente ao cancelar a atividade."
CANCELAVEIS_PELO_SOLICITANTE = {"rascunho", "submetida", "devolvida", "pre_autorizada"}

# Efeito no saldo. A ressubmissão de Devolvida reserva só o que ainda não tem reserva.
EFEITO_NO_SALDO = {
    ("rascunho", "submetida"): RESERVAR,
    ("devolvida", "submetida"): RESERVAR,
    ("submetida", "devolvida"): MANTER,
    ("submetida", "pre_autorizada"): MANTER,
    ("pre_autorizada", "autorizada"): AJUSTAR,
    ("pre_autorizada", "recusada"): LIBERAR,
    ("autorizada", "em_atendimento"): MANTER,
    ("em_atendimento", "concluida"): EXECUTAR,
}

# Notificações por etapa: (de, para) → evento que chega aos notificados.
NOTIFICACOES = {
    ("rascunho", "submetida"): "submissao",
    ("devolvida", "submetida"): "submissao",
    ("submetida", "devolvida"): "devolucao",
    ("submetida", "pre_autorizada"): "pre_autorizacao",
    ("pre_autorizada", "autorizada"): "autorizacao",
    ("pre_autorizada", "recusada"): "recusa",
    ("autorizada", "em_atendimento"): "em_atendimento",
    ("em_atendimento", "concluida"): "conclusao",
}

JUSTIFICATIVA_OBRIGATORIA = {("submetida", "devolvida"), ("pre_autorizada", "recusada")}


def _linhas(origem, para=None):
    return [t for t in TRANSICOES if t.origem == origem and (para is None or t.para == para)]


def test_cada_status_e_destino_tem_uma_unica_linha_por_origem():
    chaves = [(de, t.para, t.origem) for t in TRANSICOES for de in t.de]
    assert len(chaves) == len(set(chaves))


def test_transicoes_do_usuario_correspondem_a_tabela_de_estados():
    pares = {(de, t.para) for t in _linhas(ORIGEM_USUARIO) if t.para != "cancelada" for de in t.de}
    assert pares == set(ESTADOS)


@pytest.mark.parametrize("de,para", list(ESTADOS))
def test_cada_transicao_do_usuario_tem_perfil_saldo_justificativa_e_notificacao(de, para):
    transicao = buscar_transicao(de, para)
    assert transicao.perfis == (ESTADOS[(de, para)],)
    assert transicao.efeito_saldo == EFEITO_NO_SALDO[(de, para)]
    assert transicao.notificacao == NOTIFICACOES[(de, para)]
    assert transicao.justificativa_obrigatoria == ((de, para) in JUSTIFICATIVA_OBRIGATORIA)


def test_solicitante_cancela_ate_a_pre_autorizacao_liberando_o_saldo():
    [transicao] = [t for t in _linhas(ORIGEM_USUARIO, "cancelada") if t.perfis == (SOLICITANTE,)]
    assert transicao.de == CANCELAVEIS_PELO_SOLICITANTE
    assert transicao.efeito_saldo == LIBERAR
    assert not transicao.justificativa_obrigatoria


def test_ugp_e_super_admin_cancelam_autorizada_com_justificativa():
    """Extensão ao requisito: desfazer uma autorização já dada, com registro na timeline."""
    [transicao] = [t for t in _linhas(ORIGEM_USUARIO, "cancelada") if t.perfis != (SOLICITANTE,)]
    assert transicao.de == {"autorizada"}
    assert set(transicao.perfis) == {"ugp", "super-admin"}
    assert transicao.justificativa_obrigatoria
    assert (transicao.efeito_saldo, transicao.etapa, transicao.acao) == (LIBERAR, "cancelamento", "cancelado")


def test_sistema_cancela_toda_demanda_nao_atendida_e_notifica_solicitante_e_articulador():
    [transicao] = _linhas(ORIGEM_SISTEMA)
    assert transicao.para == "cancelada"
    assert transicao.de == CANCELAVEIS_PELO_SOLICITANTE | {"autorizada"}
    assert transicao.efeito_saldo == LIBERAR
    assert transicao.notificacao == "cancelamento_automatico"


def test_arlo_so_inicia_o_atendimento_e_conclui():
    pares = {(de, t.para) for t in _linhas(ORIGEM_ARLO) for de in t.de}
    assert pares == {("autorizada", "em_atendimento"), ("em_atendimento", "concluida")}
    for de, para in pares:
        manual, arlo = buscar_transicao(de, para), buscar_transicao(de, para, ORIGEM_ARLO)
        assert (arlo.efeito_saldo, arlo.etapa, arlo.acao, arlo.notificacao) == (
            manual.efeito_saldo, manual.etapa, manual.acao, manual.notificacao,
        )


@pytest.mark.parametrize("origem,de,para", [
    (ORIGEM_USUARIO, "rascunho", "autorizada"),
    (ORIGEM_USUARIO, "em_atendimento", "cancelada"),
    (ORIGEM_SISTEMA, "em_atendimento", "cancelada"),
    (ORIGEM_SISTEMA, "concluida", "cancelada"),
    (ORIGEM_SISTEMA, "submetida", "pre_autorizada"),
    (ORIGEM_ARLO, "pre_autorizada", "em_atendimento"),
    (ORIGEM_ARLO, "pre_autorizada", "autorizada"),
    (ORIGEM_ARLO, "autorizada", "concluida"),
])
def test_transicao_fora_da_tabela_levanta_transicao_invalida(activity_rn, usuario_fgd, origem, de, para):
    demand = DemandFactory(activity=activity_rn, status=de)

    with pytest.raises(TransicaoInvalida):
        workflow_service.executar_transicao(demand, para, ator=usuario_fgd, origem=origem)

    demand.refresh_from_db()
    assert demand.status == de


def test_cancelamento_pela_task_de_demanda_em_atendimento_levanta_transicao_invalida(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="em_atendimento")

    with pytest.raises(TransicaoInvalida):
        workflow_service.cancelar_pelo_sistema([demand], motivo="Atividade cancelada.")


def test_cancelamento_pela_task_rele_o_status_e_desfaz_a_liberacao(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """A task leu a demanda autorizada; antes do lock, a FGD iniciou o atendimento. O
    saldo já liberado volta junto com a transação, e a task é repetida."""
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    Demand.objects.filter(pk=demand.pk).update(status="autorizada")
    lida_pela_task = Demand.objects.get(pk=demand.pk)
    Demand.objects.filter(pk=demand.pk).update(status="em_atendimento")

    with pytest.raises(TransicaoInvalida):
        workflow_service.cancelar_pelo_sistema([lida_pela_task], motivo="Atividade cancelada.")

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    demand_request_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    assert allocation_territorial_rn.valor_comprometido == Decimal("1000")
    assert demand_request_rn.valor_reservado == Decimal("1000")


def test_task_de_cancelamento_e_repetida_quando_a_demanda_muda(monkeypatch, activity_rn):
    from unittest.mock import patch

    from celery.exceptions import Retry

    from apps.sgd import tasks as sgd_tasks

    def _mudou(activity_id):
        raise TransicaoInvalida(workflow_service.MENSAGEM_DEMANDA_MUDOU)

    monkeypatch.setattr(sgd_tasks, "_cancelar_demandas_da_atividade", _mudou)

    with patch.object(sgd_tasks.cancelar_demandas_da_atividade, "retry", side_effect=Retry) as retry:
        with pytest.raises(Retry):
            sgd_tasks.cancelar_demandas_da_atividade(activity_rn.pk)

    retry.assert_called_once()
    assert isinstance(retry.call_args.kwargs["exc"], TransicaoInvalida)


def test_recusar_sem_justificativa_bloqueia(activity_rn, usuario_ugp):
    demand = DemandFactory(activity=activity_rn, status="pre_autorizada")

    with pytest.raises(JustificativaObrigatoria):
        workflow_service.executar_transicao(demand, "recusada", ator=usuario_ugp, justificativa="  ")


def test_transicao_parte_de_status_desatualizado_e_recusada(activity_rn, usuario_articulador_rn):
    """Duas decisões sobre a mesma demanda lida antes: a segunda encontra outro status
    na linha travada."""
    demand = DemandFactory(activity=activity_rn, status="submetida")
    lida_antes = Demand.objects.get(pk=demand.pk)
    workflow_service.executar_transicao(demand, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar.")

    with pytest.raises(TransicaoInvalida):
        workflow_service.executar_transicao(lida_antes, "pre_autorizada", ator=usuario_articulador_rn)

    demand.refresh_from_db()
    assert demand.status == "devolvida"
    assert demand.etapas.count() == 1


def test_api_concluir_demanda_autorizada_devolve_transicao_invalida(auth_client_fgd, activity_rn):
    demand = DemandFactory(activity=activity_rn, status="autorizada")

    resposta = auth_client_fgd.post(
        f"/api/v1/sgd/demandas/{demand.pk}/concluir/", {"valores_pagos": {}}, format="json",
    )

    assert resposta.status_code == 400
    assert resposta.data["code"] == "INVALID_TRANSITION"
