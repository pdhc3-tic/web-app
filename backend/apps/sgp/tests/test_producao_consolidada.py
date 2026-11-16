"""Listagem consolidada de produção (`/sgp/producao/`) e seus indicadores."""
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.sgp.models import Production
from apps.sgp.tests.factories import (
    CulturaFactory,
    EspecieAnimalFactory,
    ProductionFactory,
    UFPAFactory,
)

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/sgp/producao/"
INDICADORES_URL = "/api/v1/sgp/producao/indicadores/"


@pytest.fixture
def ufpa_rn(municipio_rn):
    return UFPAFactory(municipio=municipio_rn, _titular_nome="Maria RN")


@pytest.fixture
def ufpa_ce(municipio_ce):
    return UFPAFactory(municipio=municipio_ce, _titular_nome="José CE")


@pytest.fixture
def milho():
    return CulturaFactory(nome="Milho")


@pytest.fixture
def feijao():
    return CulturaFactory(nome="Feijão")


def _ids(response):
    return {item["id"] for item in response.data["results"]}


def test_lista_campos_da_ufpa(ugp_client, ufpa_rn, milho, municipio_rn):
    producao = ProductionFactory(ufpa=ufpa_rn, cultura=milho)

    response = ugp_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    item = response.data["results"][0]
    assert item["id"] == producao.pk
    assert item["ufpa_id"] == ufpa_rn.pk
    assert item["ufpa_nome_titular"] == "Maria RN"
    assert item["municipio"] == municipio_rn.nome
    assert item["territorio"] == municipio_rn.territory.nome
    assert item["cultura"]["nome"] == "Milho"


def test_paginacao_page_size(ugp_client, ufpa_rn):
    ProductionFactory.create_batch(3, ufpa=ufpa_rn)

    response = ugp_client.get(LIST_URL, {"page": 2, "page_size": 2})

    assert response.data["count"] == 3
    assert len(response.data["results"]) == 1


def test_filtros(ugp_client, ufpa_rn, ufpa_ce, milho, feijao, municipio_rn, territory_ce):
    milho_rn = ProductionFactory(ufpa=ufpa_rn, cultura=milho)
    feijao_ce = ProductionFactory(ufpa=ufpa_ce, cultura=feijao)
    caprino_rn = ProductionFactory(
        ufpa=ufpa_rn, tipo=Production.TIPO_PECUARIA, cultura=None,
        especie=EspecieAnimalFactory(), area_ha=None,
    )

    assert _ids(ugp_client.get(LIST_URL, {"tipo": "agricola"})) == {milho_rn.pk, feijao_ce.pk}
    assert _ids(ugp_client.get(LIST_URL, {"cultura": feijao.pk})) == {feijao_ce.pk}
    assert _ids(ugp_client.get(LIST_URL, {"especie": caprino_rn.especie_id})) == {caprino_rn.pk}
    assert _ids(ugp_client.get(LIST_URL, {"municipio": municipio_rn.pk})) == {
        milho_rn.pk, caprino_rn.pk,
    }
    assert _ids(ugp_client.get(LIST_URL, {"territorio": territory_ce.pk})) == {feijao_ce.pk}


def test_escopo_adt_ve_so_o_proprio_territorio(auth_client_adt_rn, usuario, ufpa_rn, ufpa_ce):
    do_rn = ProductionFactory(ufpa=ufpa_rn)
    do_ce = ProductionFactory(ufpa=ufpa_ce)
    # As fixtures auth_client_* autenticam a mesma instância de APIClient; a UGP
    # precisa de um cliente próprio para não sobrescrever o login do ADT.
    cliente_ugp = APIClient()
    cliente_ugp.force_authenticate(user=usuario)

    assert _ids(auth_client_adt_rn.get(LIST_URL)) == {do_rn.pk}
    assert _ids(cliente_ugp.get(LIST_URL)) == {do_rn.pk, do_ce.pk}


def test_ufpa_inativa_fica_de_fora(ugp_client, ufpa_rn, municipio_rn):
    inativa = UFPAFactory(municipio=municipio_rn, ativo=False)
    ProductionFactory(ufpa=inativa)
    ativa = ProductionFactory(ufpa=ufpa_rn)

    assert _ids(ugp_client.get(LIST_URL)) == {ativa.pk}


def test_usuario_sem_perfil_sgp_recebe_403(auth_client_sem_acesso):
    assert auth_client_sem_acesso.get(LIST_URL).status_code == status.HTTP_403_FORBIDDEN
    assert auth_client_sem_acesso.get(INDICADORES_URL).status_code == status.HTTP_403_FORBIDDEN


def test_indicadores(ugp_client, ufpa_rn, ufpa_ce, municipio_rn, milho, feijao):
    outra_ufpa_rn = UFPAFactory(municipio=municipio_rn)
    ProductionFactory(ufpa=ufpa_rn, cultura=milho, area_ha=Decimal("2.50"))
    ProductionFactory(ufpa=outra_ufpa_rn, cultura=milho, area_ha=Decimal("1.00"))
    ProductionFactory(ufpa=ufpa_ce, cultura=feijao, area_ha=Decimal("4.00"))
    ProductionFactory(
        ufpa=ufpa_rn, tipo=Production.TIPO_PECUARIA, cultura=None,
        especie=EspecieAnimalFactory(), area_ha=None,
    )

    response = ugp_client.get(INDICADORES_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_ufpas_produtoras"] == 3
    assert response.data["area_total_ha"] == "7.50"
    assert response.data["principais_culturas"] == [
        {"nome": "Milho", "count": 2},
        {"nome": "Feijão", "count": 1},
    ]


def test_indicadores_respeitam_filtros_e_escopo(auth_client_adt_rn, ufpa_rn, ufpa_ce, milho, feijao):
    ProductionFactory(ufpa=ufpa_rn, cultura=milho, area_ha=Decimal("2.00"))
    ProductionFactory(ufpa=ufpa_ce, cultura=feijao, area_ha=Decimal("9.00"))

    response = auth_client_adt_rn.get(INDICADORES_URL, {"tipo": "agricola"})

    assert response.data["total_ufpas_produtoras"] == 1
    assert response.data["area_total_ha"] == "2.00"
    assert response.data["principais_culturas"] == [{"nome": "Milho", "count": 1}]


def test_indicadores_sem_producao(ugp_client):
    response = ugp_client.get(INDICADORES_URL)

    assert response.data == {
        "total_ufpas_produtoras": 0,
        "area_total_ha": "0.00",
        "principais_culturas": [],
    }
