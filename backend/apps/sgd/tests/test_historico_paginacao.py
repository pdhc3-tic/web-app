import pytest

from apps.sgd.models import ApprovalStep
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db

EVENTOS = 120


@pytest.fixture
def demanda_com_historico_extenso(activity_rn, solicitante_rn, usuario_ugp):
    demanda = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
    ApprovalStep.objects.bulk_create([
        ApprovalStep(demanda=demanda, etapa="pre_autorizacao", responsavel=usuario_ugp, acao="aprovado")
        for _ in range(EVENTOS)
    ])
    return demanda


def test_historico_com_limit_pagina_o_historico_extenso(auth_client_ugp, demanda_com_historico_extenso):
    url = f"/api/v1/sgd/demandas/{demanda_com_historico_extenso.pk}/historico/"

    primeira = auth_client_ugp.get(url, {"limit": 50}).json()
    ultima = auth_client_ugp.get(url, {"limit": 50, "offset": 100}).json()

    assert primeira["count"] == EVENTOS
    assert len(primeira["results"]) == 50
    assert primeira["next"] is not None
    assert len(ultima["results"]) == EVENTOS - 100
    assert ultima["next"] is None


def test_historico_sem_limit_mantem_lista_simples(auth_client_ugp, demanda_com_historico_extenso):
    response = auth_client_ugp.get(f"/api/v1/sgd/demandas/{demanda_com_historico_extenso.pk}/historico/")

    assert isinstance(response.json(), list)
    assert len(response.json()) == EVENTOS


def test_historico_respeita_escopo_de_visibilidade(auth_client_articulador_ce, demanda_com_historico_extenso):
    response = auth_client_articulador_ce.get(f"/api/v1/sgd/demandas/{demanda_com_historico_extenso.pk}/historico/")

    assert response.status_code == 404
