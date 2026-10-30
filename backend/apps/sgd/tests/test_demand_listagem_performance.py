import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgd.models import ApprovalStep, Demand, DemandRequest

pytestmark = pytest.mark.django_db

TOTAL = 10_000
LIMITE_SEGUNDOS = 2


@pytest.mark.performance
def test_listagem_com_10_mil_demandas_e_filtros_combinados_em_menos_de_2s(
    auth_client_ugp, activity_rn, solicitante_rn, territory_rn,
):
    status = ["submetida", "autorizada", "concluida", "recusada"]
    Demand.objects.bulk_create([
        Demand(
            titulo=f"Demanda {i}", activity=activity_rn, solicitante=solicitante_rn,
            status=status[i % len(status)],
        )
        for i in range(TOTAL)
    ], batch_size=1000)

    params = {
        "status": "submetida", "territorio": territory_rn.pk,
        "periodo_inicio": "2000-01-01", "limit": 50,
    }
    inicio = time.perf_counter()
    response = auth_client_ugp.get("/api/v1/sgd/demandas/", params)
    duracao = time.perf_counter() - inicio

    assert response.status_code == 200
    assert response.json()["count"] == TOTAL // len(status)
    assert len(response.json()["results"]) == 50
    assert duracao < LIMITE_SEGUNDOS, f"listagem levou {duracao:.2f}s"


def _criar_massa_com_relacionamentos(activity, solicitante, rubrica, responsavel):
    # `bulk_create` não passa pelos serviços: o total já vai com as duas solicitações de 100.
    Demand.objects.bulk_create([
        Demand(
            titulo=f"Demanda {i}", activity=activity, solicitante=solicitante, status="submetida",
            valor_estimado_total=200,
        )
        for i in range(TOTAL)
    ], batch_size=1000)
    demandas = list(Demand.objects.values_list("pk", flat=True))
    DemandRequest.objects.bulk_create([
        DemandRequest(demanda_id=pk, tipo="diaria", rubrica=rubrica, campos_json={}, valor_estimado=100, ordem=n)
        for pk in demandas for n in range(2)
    ], batch_size=1000)
    ApprovalStep.objects.bulk_create([
        ApprovalStep(demanda_id=pk, etapa="pre_autorizacao", responsavel=responsavel, acao="aprovado")
        for pk in demandas
    ], batch_size=1000)


def _consultas_da_listagem(client, params):
    with CaptureQueriesContext(connection) as consultas:
        response = client.get("/api/v1/sgd/demandas/", params)
    assert response.status_code == 200
    return len(consultas), response.json()


def test_listagem_executa_numero_fixo_de_queries_independente_do_volume(
    auth_client_ugp, activity_rn, solicitante_rn, rubrica_diarias, usuario_ugp,
):
    _criar_massa_com_relacionamentos(activity_rn, solicitante_rn, rubrica_diarias, usuario_ugp)
    filtros = {"status": "submetida", "periodo_inicio": "2000-01-01", "tipo": "diaria", "rubrica": rubrica_diarias.slug}

    pequena, corpo_pequeno = _consultas_da_listagem(auth_client_ugp, {**filtros, "limit": 5})
    grande, corpo_grande = _consultas_da_listagem(auth_client_ugp, {**filtros, "limit": 100})

    assert len(corpo_pequeno["results"]) == 5
    assert len(corpo_grande["results"]) == 100
    assert corpo_grande["count"] == TOTAL
    assert corpo_grande["results"][0]["valor_estimado_total"] == "200.00"
    assert pequena == grande
