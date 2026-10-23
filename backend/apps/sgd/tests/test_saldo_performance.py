import time
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgp.models.budget import BudgetTransaction

pytestmark = pytest.mark.django_db

LIMITE_SEGUNDOS = 0.3
HISTORICO = 5_000


def test_verificacao_de_saldo_com_historico_representativo_em_menos_de_300ms(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    BudgetTransaction.objects.bulk_create([
        BudgetTransaction(
            allocation=allocation_territorial_rn, tipo="reserva", valor=Decimal("10"), demanda_id=str(i % 500),
        )
        for i in range(HISTORICO)
    ], batch_size=1000)
    params = {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"}
    auth_client_solicitante.get("/api/v1/sgd/saldo/", params)  # aquece caches (config, sessão)

    inicio = time.perf_counter()
    response = auth_client_solicitante.get("/api/v1/sgd/saldo/", params)
    duracao = time.perf_counter() - inicio

    assert response.status_code == 200
    assert duracao < LIMITE_SEGUNDOS, f"verificação de saldo levou {duracao * 1000:.0f}ms"


def test_verificacao_de_saldo_nao_consulta_o_limite_individual_duas_vezes(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    params = {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"}
    auth_client_solicitante.get("/api/v1/sgd/saldo/", params)

    with CaptureQueriesContext(connection) as consultas:
        response = auth_client_solicitante.get("/api/v1/sgd/saldo/", params)

    assert response.status_code == 200
    limites = [q for q in consultas.captured_queries if 'FROM "sgd_demandindividuallimit"' in q["sql"]]
    assert len(limites) == 1
