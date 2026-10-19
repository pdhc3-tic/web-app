"""Escopo territorial na criação de demanda: atividade existente e criação inline."""
import pytest

from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity
from apps.sgp.tests.factories import ActivityFactory, WorkPlanAcaoFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/"


@pytest.fixture
def activity_ce(municipio_ce, solicitante_rn):
    return ActivityFactory(
        municipio=municipio_ce, tecnico_responsavel=solicitante_rn, status="planejado",
        acao=WorkPlanAcaoFactory(),
    )


def _payload_inline(municipio):
    return {
        "titulo": "Pedido de diárias",
        "activity_titulo": "Seminário Regional",
        "activity_tipo_atividade": "seminario",
        "activity_acao_id": WorkPlanAcaoFactory().pk,
        "activity_municipio_id": municipio.pk,
        "activity_data_prevista": "2026-11-01T09:00:00Z",
    }


def test_adt_cria_demanda_em_atividade_do_proprio_territorio(auth_client_solicitante, activity_rn):
    response = auth_client_solicitante.post(
        URL, {"titulo": "Pedido", "activity_id": activity_rn.pk}, format="json",
    )

    assert response.status_code == 201
    assert Demand.objects.filter(activity=activity_rn).count() == 1


def test_adt_nao_cria_demanda_em_atividade_de_outro_territorio(auth_client_solicitante, activity_ce):
    response = auth_client_solicitante.post(
        URL, {"titulo": "Pedido", "activity_id": activity_ce.pk}, format="json",
    )

    assert response.status_code == 404
    assert not Demand.objects.exists()


def test_adt_cria_atividade_inline_em_municipio_do_proprio_territorio(auth_client_solicitante, municipio_rn):
    response = auth_client_solicitante.post(URL, _payload_inline(municipio_rn), format="json")

    assert response.status_code == 201
    assert Demand.objects.filter(activity__municipio=municipio_rn).count() == 1


def test_adt_nao_cria_atividade_inline_em_municipio_de_outro_territorio(auth_client_solicitante, municipio_ce):
    response = auth_client_solicitante.post(URL, _payload_inline(municipio_ce), format="json")

    assert response.status_code == 404
    assert not Activity.objects.filter(municipio=municipio_ce).exists()
    assert not Demand.objects.exists()


def test_super_admin_cria_demanda_em_qualquer_territorio(auth_client_super_admin, activity_ce):
    response = auth_client_super_admin.post(
        URL, {"titulo": "Pedido", "activity_id": activity_ce.pk}, format="json",
    )

    assert response.status_code == 201


def test_super_admin_cria_atividade_inline_em_qualquer_territorio(auth_client_super_admin, municipio_ce):
    response = auth_client_super_admin.post(URL, _payload_inline(municipio_ce), format="json")

    assert response.status_code == 201
