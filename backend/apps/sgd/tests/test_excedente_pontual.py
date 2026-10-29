"""Excedente autorizado pela UGP na própria demanda (remanejamento emergencial, SGD-RF16)."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import TerritoryFactory
from apps.sgd.models import DemandIndividualLimit
from apps.sgd.services import demand as demand_service
from apps.sgd.services.reconciliacao import divergencias_dos_limites, divergencias_dos_totais
from apps.sgd.services.workflow import executar_transicao
from apps.sgp.models import BudgetAllocation, BudgetTransfer
from apps.sgp.tests.factories import BudgetAllocationFactory, BudgetRubricaFactory

pytestmark = pytest.mark.django_db

TRANSFERENCIAS = "/api/v1/sgd/remanejamentos/transferencias/"


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


@pytest.fixture
def demanda(demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn):
    """Pré-autorizada, com a solicitação de 1.000 reservada: limite de 5.000 e pool de 10.000."""
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    return demand


@pytest.fixture
def origem(allocation_territorial_rn, activity_rn, rubrica_diarias):
    return BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        estado=activity_rn.municipio.state, territorio=None, valor_alocado=Decimal("5000"),
    )


def _autorizar(usuario, demanda, solicitacao, valor, **corpo):
    corpo = {
        "ajustes": {str(solicitacao.pk): str(valor)}, "excedente_autorizado": True,
        "justificativa": "Mutirão antecipado pela estiagem.", **corpo,
    }
    return _cliente(usuario).post(f"/api/v1/sgd/demandas/{demanda.pk}/autorizar/", corpo, format="json")


def _limite(limite):
    limite.refresh_from_db()
    return limite


def test_excedente_remaneja_da_origem_sem_alterar_o_valor_limite(
    demanda, demand_request_rn, usuario_ugp, origem, limite_individual_rn, allocation_territorial_rn,
):
    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk)

    assert resposta.status_code == 200, resposta.data
    assert resposta.data["status"] == "autorizada"
    assert resposta.data["etapas"][-1]["excedente_autorizado"] is True
    limite = _limite(limite_individual_rn)
    assert (limite.valor_limite, limite.valor_comprometido) == (Decimal("5000"), Decimal("5000"))
    demand_request_rn.refresh_from_db()
    assert (demand_request_rn.valor_autorizado, demand_request_rn.valor_excedente) == (Decimal("5300"), Decimal("300"))

    transferencia = BudgetTransfer.objects.get()
    assert transferencia.escopo == BudgetTransfer.Escopo.PONTUAL
    assert transferencia.valor == Decimal("300")
    assert (transferencia.allocation_origem, transferencia.allocation_destino) == (origem, allocation_territorial_rn)
    assert (transferencia.saldo_origem_antes, transferencia.saldo_origem_depois) == (Decimal("5000"), Decimal("4700"))
    assert (transferencia.saldo_destino_antes, transferencia.saldo_destino_depois) == (Decimal("9000"), Decimal("9300"))
    assert (transferencia.demanda_id, transferencia.solicitacao_id) == (str(demanda.pk), str(demand_request_rn.pk))
    assert transferencia.increase_request is None
    assert transferencia.aprovado_por == usuario_ugp
    assert transferencia.motivo == f"Excedente autorizado na demanda #{demanda.pk}: Mutirão antecipado pela estiagem."
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_alocado == Decimal("10300")
    assert allocation_territorial_rn.valor_comprometido == Decimal("5300")
    assert divergencias_dos_limites() == []
    assert divergencias_dos_totais() == []


def test_excedente_cancelado_devolve_o_limite_ao_valor_original(
    demanda, demand_request_rn, usuario_ugp, origem, limite_individual_rn,
):
    """Limite de 1.000, solicitação de 1.300 autorizada com excedente e depois
    cancelada: o disponível volta a 1.000, e não a 1.300."""
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_limite=Decimal("1000"))
    assert _autorizar(usuario_ugp, demanda, demand_request_rn, "1300", origem_allocation=origem.pk).status_code == 200
    demanda.refresh_from_db()

    executar_transicao(demanda, "cancelada", ator=usuario_ugp, justificativa="Evento suspenso.")

    limite = _limite(limite_individual_rn)
    assert limite.valor_comprometido == Decimal("0")
    assert limite.saldo_disponivel == Decimal("1000")
    assert divergencias_dos_limites() == []


def test_concluida_abaixo_do_autorizado_nao_devolve_o_excedente_ao_limite(
    demanda, demand_request_rn, usuario_ugp, usuario_fgd, origem, limite_individual_rn,
):
    assert _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk).status_code == 200
    demanda.refresh_from_db()
    executar_transicao(demanda, "em_atendimento", ator=usuario_fgd)

    executar_transicao(demanda, "concluida", ator=usuario_fgd, valores_pagos={demand_request_rn.pk: Decimal("5100")})

    limite = _limite(limite_individual_rn)
    assert (limite.valor_comprometido, limite.valor_executado) == (Decimal("0"), Decimal("5000"))
    assert limite.saldo_disponivel == Decimal("0")
    demanda.refresh_from_db()
    assert demanda.valor_pago_total == Decimal("5100")


def test_sem_saldo_no_pool_remaneja_o_que_falta_nele(
    demanda, demand_request_rn, usuario_ugp, origem, limite_individual_rn, allocation_territorial_rn,
):
    """O limite cobre o aumento de 400, mas o pool só tem 100 livres: remaneja 300,
    e nada fica fora do limite."""
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("1100"))

    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "1400", origem_allocation=origem.pk)

    assert resposta.status_code == 200, resposta.data
    assert BudgetTransfer.objects.get().valor == Decimal("300")
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_excedente == Decimal("0")
    assert _limite(limite_individual_rn).valor_comprometido == Decimal("1400")


def test_acima_do_limite_e_do_pool_remaneja_o_maior_dos_dois(
    demanda, demand_request_rn, usuario_ugp, origem, limite_individual_rn, allocation_territorial_rn,
):
    """Aumento de 500 com 200 livres no limite (300 acima) e 100 livres no pool (400
    acima): remaneja 400, e só os 300 acima do limite ficam fora dele."""
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_limite=Decimal("1200"))
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("1100"))

    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "1500", origem_allocation=origem.pk)

    assert resposta.status_code == 200, resposta.data
    assert BudgetTransfer.objects.get().valor == Decimal("400")
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_excedente == Decimal("300")
    assert _limite(limite_individual_rn).valor_comprometido == Decimal("1200")


def test_excedente_nao_depende_do_nivel_atual_do_solicitante(
    demanda, demand_request_rn, solicitante_rn, usuario_ugp, origem,
):
    """O remanejamento vai para o pool da reserva, mesmo que o solicitante tenha
    perdido o território depois de submeter."""
    solicitante_rn.profiles.update(territorio=None)

    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk)

    assert resposta.status_code == 200, resposta.data


@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        ({"origem_allocation": None}, "origem_allocation"),
        ({"justificativa": ""}, "justificativa"),
        ({"excedente_autorizado": False}, "origem_allocation"),
    ],
    ids=["sem-origem", "sem-justificativa", "origem-sem-excedente"],
)
def test_pedido_de_excedente_incompleto_e_400(demanda, demand_request_rn, usuario_ugp, origem, corpo, campo):
    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", **{"origem_allocation": origem.pk, **corpo})

    assert resposta.status_code == 400
    assert campo in resposta.data
    demanda.refresh_from_db()
    assert demanda.status == "pre_autorizada"
    assert not BudgetTransfer.objects.exists()


@pytest.fixture
def origem_territorial(allocation_territorial_rn, rubrica_diarias):
    return BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.TERRITORIAL,
        territorio=TerritoryFactory(nome="Outro território", estados=["RN"]), valor_alocado=Decimal("5000"),
    )


@pytest.fixture
def origem_de_outra_rubrica(allocation_territorial_rn, activity_rn):
    return BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=BudgetRubricaFactory(slug="passagens-aereas"),
        nivel=BudgetAllocation.Nivel.ESTADUAL, estado=activity_rn.municipio.state, territorio=None,
        valor_alocado=Decimal("5000"),
    )


@pytest.mark.parametrize("nome_da_origem", ["origem_territorial", "origem_de_outra_rubrica"])
def test_origem_que_nao_pode_cobrir_o_excedente_e_400(
    request, demanda, demand_request_rn, usuario_ugp, limite_individual_rn, nome_da_origem,
):
    origem = request.getfixturevalue(nome_da_origem)

    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk)

    assert resposta.status_code == 400
    assert resposta.data["code"] == "BUSINESS_RULE"
    assert "origem_allocation" in resposta.data
    assert _limite(limite_individual_rn).valor_comprometido == Decimal("1000")
    assert not BudgetTransfer.objects.exists()


def test_excedente_sem_nada_a_exceder_e_400(demanda, demand_request_rn, usuario_ugp, origem):
    resposta = _autorizar(usuario_ugp, demanda, demand_request_rn, "1200", origem_allocation=origem.pk)

    assert resposta.status_code == 400
    assert "excedente_autorizado" in resposta.data
    demanda.refresh_from_db()
    assert demanda.status == "pre_autorizada"


def test_excedente_entra_na_trilha_de_auditoria_da_demanda(
    demanda, demand_request_rn, usuario_ugp, usuario_super_admin, origem,
):
    assert _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk).status_code == 200

    resposta = _cliente(usuario_super_admin).get(f"/api/v1/sgd/demandas/{demanda.pk}/auditoria/")

    assert resposta.status_code == 200
    assert "remanejamento.efetivado" in [entrada["acao"] for entrada in resposta.data["results"]]
    evento = AuditLog.objects.get(acao="remanejamento.efetivado")
    assert evento.valores_novos["escopo"] == "pontual"
    assert evento.valores_novos["solicitacao"] == str(demand_request_rn.pk)


# --- listagem dos remanejamentos ---------------------------------------------


@pytest.fixture
def excedente_autorizado(demanda, demand_request_rn, usuario_ugp, origem):
    assert _autorizar(usuario_ugp, demanda, demand_request_rn, "5300", origem_allocation=origem.pk).status_code == 200
    return BudgetTransfer.objects.get()


@pytest.mark.parametrize("perfil", ["usuario_ugp", "usuario_super_admin", "usuario_fgd"])
def test_coordenacao_lista_o_excedente_entre_os_remanejamentos(request, excedente_autorizado, origem, perfil):
    resposta = _cliente(request.getfixturevalue(perfil)).get(TRANSFERENCIAS)

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    item = resposta.data["results"][0]
    assert item["id"] == excedente_autorizado.pk
    assert item["escopo"] == "pontual"
    assert item["valor"] == "300.00"
    assert item["rubrica"] == "diarias"
    assert item["origem"] == {"id": origem.pk, "nivel": "estadual", "estado": "RN", "territorio": None}
    assert item["demanda_id"] == excedente_autorizado.demanda_id
    assert item["solicitacao_id"] == excedente_autorizado.solicitacao_id
    assert item["pedido"] is None
    assert "ip" not in item


@pytest.mark.parametrize(
    ("filtro", "total"),
    [("escopo=pontual", 1), ("escopo=elevacao_limite", 0), ("rubrica=diarias", 1), ("rubrica=passagens", 0)],
)
def test_filtros_da_listagem_de_remanejamentos(excedente_autorizado, usuario_ugp, filtro, total):
    resposta = _cliente(usuario_ugp).get(f"{TRANSFERENCIAS}?{filtro}")

    assert resposta.status_code == 200
    assert resposta.data["count"] == total


def test_filtro_por_demanda_na_listagem_de_remanejamentos(excedente_autorizado, demanda, usuario_ugp):
    cliente = _cliente(usuario_ugp)

    assert cliente.get(f"{TRANSFERENCIAS}?demanda={demanda.pk}").data["count"] == 1
    assert cliente.get(f"{TRANSFERENCIAS}?demanda={demanda.pk + 1}").data["count"] == 0
    assert cliente.get(f"{TRANSFERENCIAS}?demanda=abc").status_code == 400


def test_escopo_invalido_na_listagem_de_remanejamentos_e_400(usuario_ugp):
    assert _cliente(usuario_ugp).get(f"{TRANSFERENCIAS}?escopo=outro").status_code == 400


@pytest.mark.parametrize("perfil", ["solicitante_rn", "usuario_articulador_rn"])
def test_quem_nao_e_da_coordenacao_nao_lista_remanejamentos(request, perfil):
    assert _cliente(request.getfixturevalue(perfil)).get(TRANSFERENCIAS).status_code == 403
