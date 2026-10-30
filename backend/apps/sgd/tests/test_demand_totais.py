"""Totais materializados na demanda: estimado, autorizado e pago."""
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgd.models import DemandTypeRubricaMapping
from apps.sgd.services import demand as demand_service
from apps.sgd.services.workflow import executar_transicao
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory, DemandTypeRubricaMappingFactory

pytestmark = pytest.mark.django_db

LISTAGEM = "/api/v1/sgd/demandas/"

CAMPOS_GRAFICO = {
    "tipo_material": "banner", "quantidade": 1,
    "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
}


@pytest.fixture
def grafico_em_diarias(rubrica_diarias):
    DemandTypeRubricaMapping.objects.filter(tipo="grafico").delete()
    return DemandTypeRubricaMappingFactory(tipo="grafico", rubrica=rubrica_diarias)


def _totais(demanda):
    demanda.refresh_from_db()
    return demanda.valor_estimado_total, demanda.valor_autorizado_total, demanda.valor_pago_total


def _adicionar(demanda, valor):
    return demand_service.adicionar_solicitacao(
        demanda, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=Decimal(valor),
    )


def test_total_estimado_acompanha_inclusao_edicao_e_remocao(demand_rascunho_rn, solicitante_rn, grafico_em_diarias):
    primeira = _adicionar(demand_rascunho_rn, "500")
    segunda = _adicionar(demand_rascunho_rn, "300")
    assert _totais(demand_rascunho_rn)[0] == Decimal("800")

    demand_service.atualizar_solicitacao(primeira, usuario=solicitante_rn, valor_estimado=Decimal("700"))
    assert _totais(demand_rascunho_rn)[0] == Decimal("1000")

    demand_service.remover_solicitacao(segunda, usuario=solicitante_rn)
    assert _totais(demand_rascunho_rn)[0] == Decimal("700")


@pytest.fixture
def demanda_pre_autorizada(demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    return demand


def test_autorizacao_com_ajuste_grava_o_total_autorizado(demanda_pre_autorizada, demand_request_rn, usuario_ugp):
    executar_transicao(
        demanda_pre_autorizada, "autorizada", ator=usuario_ugp, ajustes={demand_request_rn.pk: Decimal("800")},
    )

    assert _totais(demanda_pre_autorizada) == (Decimal("1000"), Decimal("800"), Decimal("0"))


def test_conclusao_grava_o_total_pago(demanda_pre_autorizada, demand_request_rn, usuario_ugp, usuario_fgd):
    executar_transicao(demanda_pre_autorizada, "autorizada", ator=usuario_ugp)
    executar_transicao(demanda_pre_autorizada, "em_atendimento", ator=usuario_fgd)

    executar_transicao(
        demanda_pre_autorizada, "concluida", ator=usuario_fgd, valores_pagos={demand_request_rn.pk: Decimal("900")},
    )

    assert _totais(demanda_pre_autorizada) == (Decimal("1000"), Decimal("1000"), Decimal("900"))


def _consultas_da_listagem(client):
    with CaptureQueriesContext(connection) as consultas:
        resposta = client.get(LISTAGEM)
    assert resposta.status_code == 200
    return len(consultas), resposta.json()


def test_listagem_nao_faz_mais_consultas_com_mais_solicitacoes(auth_client_ugp, activity_rn, solicitante_rn):
    demanda = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
    DemandRequestFactory(demanda=demanda, valor_estimado=100)
    com_uma, _ = _consultas_da_listagem(auth_client_ugp)

    for _ in range(19):
        DemandRequestFactory(demanda=demanda, valor_estimado=100)
    com_vinte, corpo = _consultas_da_listagem(auth_client_ugp)

    assert com_vinte == com_uma
    assert corpo["results"][0]["valor_estimado_total"] == "2000.00"


@pytest.fixture
def demandas_por_valor(activity_rn, solicitante_rn):
    demandas = {}
    for valor in (300, 100, 200):
        demanda = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
        DemandRequestFactory(demanda=demanda, valor_estimado=valor)
        demandas[valor] = demanda.pk
    return demandas


@pytest.mark.parametrize(
    ("ordering", "valores"),
    [("valor_estimado_total", [100, 200, 300]), ("-valor_estimado_total", [300, 200, 100])],
)
def test_listagem_ordena_pelo_total_estimado(auth_client_ugp, demandas_por_valor, ordering, valores):
    resposta = auth_client_ugp.get(LISTAGEM, {"ordering": ordering})

    assert resposta.status_code == 200
    assert [item["id"] for item in resposta.json()["results"]] == [demandas_por_valor[v] for v in valores]


def test_listagem_com_ordenacao_desconhecida_e_400(auth_client_ugp):
    resposta = auth_client_ugp.get(LISTAGEM, {"ordering": "titulo"})

    assert resposta.status_code == 400
    assert "ordering" in resposta.json()
