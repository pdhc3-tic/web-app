"""A tabela `TRANSICOES` contra as tabelas de estados, de efeito no saldo e de
notificações do documento de requisitos do SGD, transcritas aqui."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification, TipoNotificacao
from apps.sgd.exceptions import JustificativaObrigatoria, RegraDeNegocio, TransicaoInvalida
from apps.sgd.models.demand import Demand
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.arlo_import import processar_importacao
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

# Fixtures e helpers compartilhados com a suíte de integração Arlo.
from apps.sgd.tests.test_arlo_integration import _importar, _linha, storage_local  # noqa: F401

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

EMAIL_E_IN_APP = {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}

# Notificações por etapa: (de, para) → (notificados, canais).
NOTIFICADOS = {
    ("rascunho", "submetida"): ({"articulador"}, EMAIL_E_IN_APP),
    ("submetida", "devolvida"): ({"solicitante"}, EMAIL_E_IN_APP),
    ("submetida", "pre_autorizada"): ({"ugp"}, EMAIL_E_IN_APP),
    ("pre_autorizada", "autorizada"): ({"solicitante", "fgd"}, EMAIL_E_IN_APP),
    ("pre_autorizada", "recusada"): ({"solicitante"}, EMAIL_E_IN_APP),
    ("autorizada", "em_atendimento"): ({"solicitante"}, {TipoNotificacao.IN_APP}),
    ("em_atendimento", "concluida"): ({"solicitante"}, EMAIL_E_IN_APP),
}


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


# ── Notificados e canais, executando cada transição ─────────────────────────

_ANTES = {
    "rascunho": [],
    "submetida": ["submetida"],
    "pre_autorizada": ["submetida", "pre_autorizada"],
    "autorizada": ["submetida", "pre_autorizada", "autorizada"],
    "em_atendimento": ["submetida", "pre_autorizada", "autorizada", "em_atendimento"],
}
_QUEM_FAZ = {
    "submetida": "solicitante", "devolvida": "articulador", "pre_autorizada": "articulador",
    "autorizada": "ugp", "recusada": "ugp", "em_atendimento": "fgd", "concluida": "fgd",
}
_EXIGEM_JUSTIFICATIVA = {para for _, para in JUSTIFICATIVA_OBRIGATORIA}


@pytest.fixture
def atores(solicitante_rn, usuario_articulador_rn, usuario_ugp, usuario_fgd):
    return {"solicitante": solicitante_rn, "articulador": usuario_articulador_rn, "ugp": usuario_ugp, "fgd": usuario_fgd}


@pytest.fixture(autouse=True)
def sem_envio_de_email():
    with patch("apps.core.tasks.notifications.send_email_notification.delay"):
        yield


def _levar(demand, destino, atores):
    dados = {}
    if destino in _EXIGEM_JUSTIFICATIVA:
        dados["justificativa"] = "Motivo."
    if destino == "concluida":
        dados["valores_pagos"] = {s.pk: s.valor_estimado for s in demand.solicitacoes.all()}
    workflow_service.executar_transicao(demand, destino, ator=atores[_QUEM_FAZ[destino]], **dados)


def _notificados(demand):
    return set(
        Notification.objects.filter(link__endswith=f"/sgd/demandas/{demand.pk}")
        .exclude(evento="demand_semaforo_mudou").values_list("user_id", "tipo")
    )


@pytest.mark.parametrize("de,para", list(NOTIFICADOS))
def test_cada_transicao_notifica_quem_a_tabela_manda_pelos_canais_dela(
    de, para, demand_request_rn, atores, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    for passo in _ANTES[de]:
        _levar(demand, passo, atores)
    Notification.objects.all().delete()

    _levar(demand, para, atores)

    papeis, canais = NOTIFICADOS[(de, para)]
    assert _notificados(demand) == {(atores[papel].pk, canal) for papel in papeis for canal in canais}


def test_cancelamento_automatico_notifica_solicitante_e_articulador_por_email_e_in_app(
    demand_request_rn, atores, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    _levar(demand, "submetida", atores)
    Notification.objects.all().delete()

    workflow_service.cancelar_pelo_sistema([demand], motivo="Atividade cancelada.")

    assert _notificados(demand) == {
        (atores[papel].pk, canal) for papel in ("solicitante", "articulador") for canal in EMAIL_E_IN_APP
    }


# ── Importação do Arlo ──────────────────────────────────────────────────────

def test_status_que_a_importacao_aceita_vem_da_tabela():
    assert workflow_service.STATUS_PAGAVEIS_PELO_ARLO == {"autorizada", "em_atendimento"}


@pytest.mark.parametrize(
    "status", ["rascunho", "submetida", "devolvida", "pre_autorizada", "concluida", "recusada", "cancelada"],
)
def test_importacao_recusa_a_linha_de_demanda_fora_da_tabela_sem_mexer_no_saldo(
    status, demand_request_rn, solicitante_rn, usuario_fgd, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    Demand.objects.filter(pk=demand_request_rn.demanda_id).update(status=status)

    importacao = processar_importacao(_importar([_linha(demand_request_rn)], usuario_fgd))

    assert importacao.registros_ok == 0
    assert [erro["campo"] for erro in importacao.erros_json] == ["demanda_id"]
    demand = Demand.objects.get(pk=demand_request_rn.demanda_id)
    assert demand.status == status
    assert not demand.etapas.exists()
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado) == (Decimal("1000"), 0)
    assert (allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado) == (
        Decimal("1000"), 0,
    )


# ── Task de cancelamento ────────────────────────────────────────────────────

def test_cancelamento_pela_task_aceita_status_que_mudou_dentro_dos_cancelaveis(activity_rn):
    """Entre a leitura e o lock a demanda foi pré-autorizada: continua cancelável, e
    a auditoria registra o status de onde ela saiu de fato."""
    demand = DemandFactory(activity=activity_rn, status="submetida")
    lida_pela_task = Demand.objects.get(pk=demand.pk)
    Demand.objects.filter(pk=demand.pk).update(status="pre_autorizada")

    workflow_service.cancelar_pelo_sistema([lida_pela_task], motivo="Atividade cancelada.")

    demand.refresh_from_db()
    assert demand.status == "cancelada"
    ultima = AuditLog.objects.filter(entidade="Demand", entidade_id=str(demand.pk)).latest("id")
    assert ultima.valores_anteriores == {"status": "pre_autorizada"}


def test_task_registra_a_falha_quando_as_tentativas_acabam(monkeypatch, activity_rn):
    from apps.sgd import tasks as sgd_tasks

    def _mudou(activity_id):
        raise TransicaoInvalida(workflow_service.MENSAGEM_DEMANDA_MUDOU)

    monkeypatch.setattr(sgd_tasks, "_cancelar_demandas_da_atividade", _mudou)

    with patch.object(sgd_tasks.cancelar_demandas_da_atividade, "max_retries", 0), \
            patch.object(sgd_tasks, "sentry_sdk") as sentry:
        with pytest.raises(TransicaoInvalida):
            sgd_tasks.cancelar_demandas_da_atividade(activity_rn.pk)

    sentry.capture_exception.assert_called_once()


# ── Dados da ação ───────────────────────────────────────────────────────────

def test_autorizar_com_valor_zero_e_recusado(
    demand_request_rn, solicitante_rn, usuario_ugp, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    Demand.objects.filter(pk=demand.pk).update(status="pre_autorizada")
    demand.refresh_from_db()

    with pytest.raises(RegraDeNegocio):
        workflow_service.executar_transicao(
            demand, "autorizada", ator=usuario_ugp, ajustes={demand_request_rn.pk: Decimal("0")},
        )


def test_dado_desconhecido_nao_e_ignorado_em_silencio(activity_rn, usuario_ugp):
    demand = DemandFactory(activity=activity_rn, status="pre_autorizada")

    with pytest.raises(TypeError):
        workflow_service.executar_transicao(demand, "autorizada", ator=usuario_ugp, ajuste={})


def test_justificativa_nula_conta_como_vazia(activity_rn, usuario_fgd, usuario_ugp):
    atendida = DemandFactory(activity=activity_rn, status="autorizada")
    workflow_service.executar_transicao(atendida, "em_atendimento", ator=usuario_fgd, justificativa=None)
    assert atendida.etapas.get().justificativa == ""

    recusada = DemandFactory(activity=activity_rn, status="pre_autorizada")
    with pytest.raises(JustificativaObrigatoria):
        workflow_service.executar_transicao(recusada, "recusada", ator=usuario_ugp, justificativa=None)


def test_cancelar_demanda_em_atendimento_explica_que_nao_pode_ser_cancelada(activity_rn, solicitante_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="em_atendimento")

    with pytest.raises(TransicaoInvalida, match="não pode ser cancelada"):
        demand_service.cancelar_demanda(demand, usuario=solicitante_rn)


def test_api_cancelar_demanda_de_outra_pessoa_e_403(auth_client_ugp, activity_rn):
    """A UGP só cancela demanda autorizada; nas demais, o cancelamento é do solicitante."""
    demand = DemandFactory(activity=activity_rn, status="submetida")

    resposta = auth_client_ugp.post(f"/api/v1/sgd/demandas/{demand.pk}/cancelar/", {"motivo": "x"}, format="json")

    assert resposta.status_code == 403
    demand.refresh_from_db()
    assert demand.status == "submetida"
