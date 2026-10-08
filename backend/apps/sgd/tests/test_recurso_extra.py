"""Solicitação de recurso extra (SGP §6.6): pedido, parecer, decisão da UGP e remanejamento."""
from decimal import Decimal

import pytest
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification
from apps.sgd.models import DemandIndividualLimit
from apps.sgd.services import demand as demand_service
from apps.sgd.tests.factories import BudgetIncreaseRequestFactory
from apps.sgp.models import BudgetAllocation, BudgetIncreaseRequest, BudgetTransfer
from apps.sgp.tests.factories import ActivityFactory, BudgetAllocationFactory, WorkPlanAcaoFactory

pytestmark = pytest.mark.django_db

DEMANDAS = "/api/v1/sgd/demandas/"
REMANEJAMENTOS = "/api/v1/sgd/remanejamentos/"
JUSTIFICATIVA = "Limite individual esgotado antes do fim do período."


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


@pytest.fixture
def demanda(demand_request_rn, allocation_territorial_rn, limite_individual_rn):
    """Demanda em rascunho cujo pedido de R$ 1.000 só cabe depois de aumentar o limite."""
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_limite=Decimal("300"))
    return demand_request_rn.demanda


def _solicitar(user, demanda, **corpo):
    corpo = {"rubrica": "diarias", "valor_solicitado": "700", "justificativa": JUSTIFICATIVA, **corpo}
    return _cliente(user).post(f"{DEMANDAS}{demanda.pk}/solicitar-recurso-extra/", corpo, format="json")


def _acao(user, pedido_id, nome, corpo=None):
    return _cliente(user).post(f"{REMANEJAMENTOS}{pedido_id}/{nome}/", corpo or {}, format="json")


@pytest.fixture
def pedido(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda)
    assert resposta.status_code == 201, resposta.data
    return BudgetIncreaseRequest.objects.get(pk=resposta.data["id"])


@pytest.fixture
def pedido_com_parecer(pedido, usuario_articulador_rn):
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."}).status_code == 200
    pedido.refresh_from_db()
    return pedido


def _limite(solicitante, rubrica):
    return DemandIndividualLimit.objects.get(solicitante=solicitante, rubrica=rubrica).valor_limite


# ── Criação ──────────────────────────────────────────────────────────────────

def test_solicitante_cria_pedido_a_partir_da_demanda_bloqueada(demanda, solicitante_rn, rubrica_diarias):
    resposta = _solicitar(solicitante_rn, demanda)

    assert resposta.status_code == 201
    assert resposta.data["status"] == "submetida"
    assert resposta.data["rubrica"] == "diarias"
    assert resposta.data["demanda_id"] == str(demanda.pk)
    assert resposta.data["activity"] == demanda.activity_id
    assert resposta.data["user"] == solicitante_rn.pk
    assert Decimal(resposta.data["valor_solicitado"]) == Decimal("700")


def test_pedido_pode_ficar_em_rascunho(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda, submeter=False)

    assert resposta.status_code == 201
    assert resposta.data["status"] == "rascunho"


def test_pedido_exige_solicitacao_na_rubrica_da_demanda(demanda, solicitante_rn):
    from apps.sgp.tests.factories import BudgetRubricaFactory

    BudgetRubricaFactory(slug="passagens-aereas", nome="Passagens")

    assert _solicitar(solicitante_rn, demanda, rubrica="passagens-aereas").status_code == 400


@pytest.mark.parametrize("status", ["submetida", "pre_autorizada", "autorizada", "concluida", "cancelada"])
def test_so_demanda_em_rascunho_ou_devolvida_pede_recurso_extra(demanda, solicitante_rn, status):
    demanda.status = status
    demanda.save(update_fields=["status"])

    assert _solicitar(solicitante_rn, demanda).status_code == 400


def test_valor_e_justificativa_sao_obrigatorios(demanda, solicitante_rn):
    assert _solicitar(solicitante_rn, demanda, valor_solicitado="0").status_code == 400
    assert _solicitar(solicitante_rn, demanda, justificativa="  ").status_code == 400


def test_outro_usuario_nao_pede_recurso_extra_para_a_demanda(demanda, usuario_articulador_rn, usuario_ugp):
    assert _solicitar(usuario_articulador_rn, demanda).status_code == 403
    assert _solicitar(usuario_ugp, demanda).status_code == 403


# ── Listagem e escopo ────────────────────────────────────────────────────────

@pytest.fixture
def pedido_do_ce(municipio_ce, territory_ce):
    from apps.core.tests.factories import RoleFactory, UserFactory

    role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
    usuario = UserFactory(email="adt.ce@test.com", profiles=[(role, territory_ce)])
    atividade = ActivityFactory(municipio=municipio_ce, acao=WorkPlanAcaoFactory())
    return BudgetIncreaseRequestFactory(user=usuario, activity=atividade, status="com_parecer")


def _ids(resposta):
    return {item["id"] for item in resposta.data["results"]}


def test_ugp_ve_a_fila_de_pedidos_com_parecer_por_padrao(pedido, pedido_com_parecer, pedido_do_ce, usuario_ugp):
    resposta = _cliente(usuario_ugp).get(REMANEJAMENTOS)

    assert resposta.status_code == 200
    assert _ids(resposta) == {pedido_com_parecer.pk, pedido_do_ce.pk}


def test_ugp_ve_todos_os_status_com_filtro(pedido, pedido_do_ce, usuario_ugp):
    todos = _cliente(usuario_ugp).get(f"{REMANEJAMENTOS}?status=todos")
    submetidos = _cliente(usuario_ugp).get(f"{REMANEJAMENTOS}?status=submetida&status=devolvida")

    assert _ids(todos) == {pedido.pk, pedido_do_ce.pk}
    assert _ids(submetidos) == {pedido.pk}


def test_articulador_so_ve_os_pedidos_do_proprio_estado(pedido, pedido_do_ce, usuario_articulador_rn):
    resposta = _cliente(usuario_articulador_rn).get(REMANEJAMENTOS)

    assert _ids(resposta) == {pedido.pk}
    assert _cliente(usuario_articulador_rn).get(f"{REMANEJAMENTOS}{pedido_do_ce.pk}/").status_code == 404


def test_solicitante_so_ve_os_proprios_pedidos(pedido, pedido_do_ce, solicitante_rn):
    resposta = _cliente(solicitante_rn).get(REMANEJAMENTOS)

    assert _ids(resposta) == {pedido.pk}
    assert _cliente(solicitante_rn).get(f"{REMANEJAMENTOS}{pedido_do_ce.pk}/").status_code == 404


def test_fgd_le_mas_nao_decide(pedido_com_parecer, usuario_fgd):
    assert _cliente(usuario_fgd).get(f"{REMANEJAMENTOS}{pedido_com_parecer.pk}/").status_code == 200
    assert _acao(usuario_fgd, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"}).status_code == 403


def test_listagem_exige_autenticacao():
    assert APIClient().get(REMANEJAMENTOS).status_code == 401


# ── Máquina de estados ───────────────────────────────────────────────────────

def test_rascunho_so_vai_para_submetida(demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    pedido_id = _solicitar(solicitante_rn, demanda, submeter=False).data["id"]

    assert _acao(usuario_articulador_rn, pedido_id, "parecer", {"parecer": "x"}).status_code == 400
    assert _acao(usuario_ugp, pedido_id, "decidir", {"decisao": "aprovar"}).status_code == 400
    assert _acao(solicitante_rn, pedido_id, "submeter").data["status"] == "submetida"


def test_ciclo_completo_com_devolucao_e_reenvio(pedido, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    devolvido = _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": "Detalhe o valor."})
    assert devolvido.data["status"] == "devolvida"
    assert devolvido.data["parecer_articulador"] == "Detalhe o valor."

    editado = _cliente(solicitante_rn).patch(
        f"{REMANEJAMENTOS}{pedido.pk}/", {"valor_solicitado": "650", "justificativa": "Valor corrigido."}, format="json",
    )
    assert editado.status_code == 200
    assert Decimal(editado.data["valor_solicitado"]) == Decimal("650")

    assert _acao(solicitante_rn, pedido.pk, "submeter").data["status"] == "submetida"
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."}).data["status"] == "com_parecer"
    decidido = _acao(usuario_ugp, pedido.pk, "decidir", {"decisao": "aprovar"})
    assert decidido.data["status"] == "aprovada"
    assert decidido.data["decidido_por"] == usuario_ugp.pk
    assert decidido.data["decidido_em"] is not None


def test_edicao_so_em_rascunho_ou_devolvida(pedido, solicitante_rn):
    resposta = _cliente(solicitante_rn).patch(f"{REMANEJAMENTOS}{pedido.pk}/", {"justificativa": "x"}, format="json")

    assert resposta.status_code == 400


def test_pedido_decidido_nao_muda_mais(pedido_com_parecer, usuario_ugp, usuario_articulador_rn):
    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"}).status_code == 200

    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "x"}).status_code == 400
    assert _acao(usuario_articulador_rn, pedido_com_parecer.pk, "devolver", {"justificativa": "x"}).status_code == 400


def test_decisao_exige_parecer_antes(pedido, usuario_ugp):
    assert _acao(usuario_ugp, pedido.pk, "decidir", {"decisao": "aprovar"}).status_code == 400


def test_parecer_e_devolucao_exigem_texto(pedido, usuario_articulador_rn):
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "  "}).status_code == 400
    assert _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": ""}).status_code == 400


def test_so_o_articulador_do_estado_emite_parecer(pedido, solicitante_rn, usuario_ugp, usuario_articulador_ce):
    assert _acao(solicitante_rn, pedido.pk, "parecer", {"parecer": "x"}).status_code == 403
    assert _acao(usuario_ugp, pedido.pk, "parecer", {"parecer": "x"}).status_code == 403
    assert _acao(usuario_articulador_ce, pedido.pk, "parecer", {"parecer": "x"}).status_code == 404


def test_so_a_ugp_decide(pedido_com_parecer, solicitante_rn, usuario_articulador_rn):
    assert _acao(solicitante_rn, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"}).status_code == 403
    assert _acao(usuario_articulador_rn, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"}).status_code == 403


def test_so_o_solicitante_submete_e_edita(demanda, solicitante_rn, usuario_articulador_rn):
    pedido_id = _solicitar(solicitante_rn, demanda, submeter=False).data["id"]

    assert _acao(usuario_articulador_rn, pedido_id, "submeter").status_code == 403
    assert _cliente(usuario_articulador_rn).patch(
        f"{REMANEJAMENTOS}{pedido_id}/", {"justificativa": "x"}, format="json",
    ).status_code == 403


# ── Decisão: efeito no limite ────────────────────────────────────────────────

def test_aprovacao_eleva_o_limite_e_libera_a_submissao(
    demanda, pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias,
):
    with pytest.raises(ValidationError), transaction.atomic():
        demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"})

    assert resposta.status_code == 200
    assert Decimal(resposta.data["valor_aprovado"]) == Decimal("700")
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1000")
    demanda.refresh_from_db()
    assert demanda.status == "rascunho"  # não é submetida sozinha
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


def test_recusa_mantem_o_bloqueio_da_demanda(demanda, pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "Sem saldo."})

    assert resposta.status_code == 200
    assert resposta.data["status"] == "recusada"
    assert resposta.data["valor_aprovado"] is None
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    with pytest.raises(ValidationError), transaction.atomic():
        demand_service.submeter_demanda(demanda, usuario=solicitante_rn)


def test_recusa_sem_justificativa_retorna_400(pedido_com_parecer, usuario_ugp):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar"})

    assert resposta.status_code == 400
    assert "justificativa" in resposta.data
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"


def test_aprovacao_parcial_eleva_o_limite_so_pelo_valor_aprovado(
    pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias,
):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        "decisao": "aprovar_parcialmente", "valor_aprovado": "400", "justificativa": "Só há saldo para parte.",
    })

    assert resposta.status_code == 200
    assert resposta.data["status"] == "aprovada_parcialmente"
    assert Decimal(resposta.data["valor_aprovado"]) == Decimal("400")
    assert resposta.data["justificativa_decisao"] == "Só há saldo para parte."
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("700")


@pytest.mark.parametrize("corpo", [
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "400"},
    {"decisao": "aprovar_parcialmente", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "700", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "900", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "0", "justificativa": "x"},
    {"decisao": "talvez"},
])
def test_decisao_invalida_retorna_400(pedido_com_parecer, usuario_ugp, rubrica_diarias, solicitante_rn, corpo):
    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", corpo).status_code == 400
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_aprovacao_cria_o_limite_quando_o_usuario_nao_tem(pedido_com_parecer, usuario_ugp, solicitante_rn, rubrica_diarias):
    DemandIndividualLimit.objects.filter(solicitante=solicitante_rn).delete()

    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"})

    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("700")


# ── Pool territorial e remanejamento ─────────────────────────────────────────

@pytest.fixture
def alocacao_estadual(allocation_territorial_rn, activity_rn, rubrica_diarias):
    return BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        estado=activity_rn.municipio.state, territorio=None, valor_alocado=Decimal("50000"),
    )


def test_pool_com_saldo_nao_gera_alerta_nem_remanejamento(pedido_com_parecer, usuario_ugp):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"})

    assert resposta.data["alerta_pool_insuficiente"] is False
    assert resposta.data["transferencia_id"] is None
    assert not BudgetTransfer.objects.exists()


def test_pool_sem_saldo_alerta_a_ugp(pedido_com_parecer, usuario_ugp, allocation_territorial_rn, solicitante_rn, rubrica_diarias):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar"})

    assert resposta.status_code == 200
    assert resposta.data["alerta_pool_insuficiente"] is True
    assert resposta.data["transferencia_id"] is None
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1000")


def test_remanejamento_de_pool_estadual_cobre_o_que_falta(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        "decisao": "aprovar", "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 200, resposta.data
    assert resposta.data["alerta_pool_insuficiente"] is False
    transferencia = BudgetTransfer.objects.get(pk=resposta.data["transferencia_id"])
    assert transferencia.tipo == "entre_niveis"
    assert transferencia.valor == Decimal("500")  # 700 aprovados − 200 que o pool já tinha
    assert (transferencia.saldo_origem_antes, transferencia.saldo_origem_depois) == (Decimal("50000"), Decimal("49500"))
    assert (transferencia.saldo_destino_antes, transferencia.saldo_destino_depois) == (Decimal("200"), Decimal("700"))
    assert transferencia.aprovado_por == usuario_ugp
    assert transferencia.increase_request == pedido_com_parecer
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_alocado == Decimal("700")


def test_remanejamento_so_pode_vir_de_saldo_estadual_ou_nacional(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, solicitante_rn, rubrica_diarias,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    outra_territorial = BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, valor_alocado=Decimal("9000"),
    )

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        "decisao": "aprovar", "origem_allocation": outra_territorial.pk,
    })

    assert resposta.status_code == 400
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_remanejamento_sem_saldo_na_origem_desfaz_a_decisao(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual, solicitante_rn, rubrica_diarias,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    BudgetAllocation.objects.filter(pk=alocacao_estadual.pk).update(valor_alocado=Decimal("100"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        "decisao": "aprovar", "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 400
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    assert not BudgetTransfer.objects.exists()


def test_remanejamento_registrado_e_imutavel(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "aprovar", "origem_allocation": alocacao_estadual.pk})
    transferencia = BudgetTransfer.objects.get()

    transferencia.motivo = "adulterado"
    with pytest.raises(ValueError):
        transferencia.save()
    from django.db.models import ProtectedError
    with pytest.raises(ProtectedError):
        transferencia.delete()


# ── Auditoria e notificações ─────────────────────────────────────────────────

def test_toda_decisao_gera_auditoria(pedido_com_parecer, usuario_ugp, solicitante_rn):
    resposta = _cliente(usuario_ugp).post(
        f"{REMANEJAMENTOS}{pedido_com_parecer.pk}/decidir/", {"decisao": "aprovar"}, format="json",
        REMOTE_ADDR="198.51.100.9",
    )

    assert resposta.status_code == 200
    decisao = AuditLog.objects.get(entidade="BudgetIncreaseRequest", acao="recurso_extra.decidido_aprovar")
    assert decisao.user == usuario_ugp
    assert decisao.ip == "198.51.100.9"
    assert decisao.valores_anteriores == {"status": "com_parecer"}
    assert decisao.valores_novos["status"] == "aprovada"
    aumento = AuditLog.objects.get(entidade="DemandIndividualLimit", acao="aumento_limite")
    assert aumento.valores_anteriores == {"valor_limite": "300.00"}
    assert aumento.valores_novos["valor_limite"] == "1000.00"
    assert aumento.valores_novos["pedido"] == pedido_com_parecer.pk


def test_recusa_tambem_gera_auditoria(pedido_com_parecer, usuario_ugp):
    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "Sem saldo."})

    entrada = AuditLog.objects.get(entidade="BudgetIncreaseRequest", acao="recurso_extra.decidido_recusar")
    assert entrada.valores_novos["status"] == "recusada"
    assert not AuditLog.objects.filter(acao="aumento_limite").exists()


def test_cada_transicao_do_pedido_e_auditada(pedido, usuario_articulador_rn):
    _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."})

    acoes = list(
        AuditLog.objects.filter(entidade="BudgetIncreaseRequest", entidade_id=str(pedido.pk))
        .order_by("id").values_list("acao", flat=True)
    )
    assert acoes == ["recurso_extra.criado", "recurso_extra.submetido", "recurso_extra.parecer_emitido"]


def test_notificacoes_a_cada_etapa(demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    pedido_id = _solicitar(solicitante_rn, demanda).data["id"]
    assert Notification.objects.filter(user=usuario_articulador_rn, evento="recurso_extra_submetido").exists()

    _acao(usuario_articulador_rn, pedido_id, "parecer", {"parecer": "Procede."})
    assert Notification.objects.filter(user=usuario_ugp, evento="recurso_extra_com_parecer").exists()

    _acao(usuario_ugp, pedido_id, "decidir", {"decisao": "aprovar"})
    assert Notification.objects.filter(user=solicitante_rn, evento="recurso_extra_decidido").exists()


def test_devolucao_notifica_o_solicitante(pedido, solicitante_rn, usuario_articulador_rn):
    _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": "Detalhe o valor."})

    assert Notification.objects.filter(user=solicitante_rn, evento="recurso_extra_devolvido").exists()
