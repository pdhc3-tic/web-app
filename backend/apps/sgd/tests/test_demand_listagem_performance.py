import time

import pytest

from apps.sgd.models import Demand

pytestmark = pytest.mark.django_db

TOTAL = 10_000
LIMITE_SEGUNDOS = 2


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
