import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgd.models import Demand, DemandRequest

pytestmark = pytest.mark.django_db

TOTAL = 5_000
LIMITE_SEGUNDOS = 2
URL = "/api/v1/sgd/painel/rubricas/"


def test_painel_por_rubrica_com_muitas_solicitacoes_em_menos_de_2s_e_queries_fixas(
    auth_client_ugp, activity_rn, solicitante_rn, rubrica_diarias,
):
    status = ["submetida", "autorizada", "concluida", "recusada"]
    Demand.objects.bulk_create([
        Demand(titulo=f"Demanda {i}", activity=activity_rn, solicitante=solicitante_rn, status=status[i % 4])
        for i in range(TOTAL)
    ], batch_size=1000)
    DemandRequest.objects.bulk_create([
        DemandRequest(
            demanda_id=pk, tipo="diaria", rubrica=rubrica_diarias, campos_json={},
            valor_estimado=100, valor_autorizado=80, ordem=0,
        )
        for pk in Demand.objects.values_list("pk", flat=True)
    ], batch_size=1000)

    inicio = time.perf_counter()
    with CaptureQueriesContext(connection) as consultas:
        response = auth_client_ugp.get(URL)
    duracao = time.perf_counter() - inicio

    assert response.status_code == 200
    linha = next(l for l in response.json() if l["rubrica_slug"] == rubrica_diarias.slug)
    # submetida + autorizada + concluida = 3 de cada 4 demandas, R$ 100 cada
    assert linha["solicitado"] == f"{TOTAL * 3 // 4 * 100}.00"
    # autorizada + concluida = 2 de cada 4, R$ 80 cada
    assert linha["autorizado"] == f"{TOTAL * 2 // 4 * 80}.00"
    assert duracao < LIMITE_SEGUNDOS, f"painel levou {duracao:.2f}s"
    agregacoes = [q for q in consultas.captured_queries if 'FROM "sgd_demandrequest"' in q["sql"]]
    assert len(agregacoes) == 1
