from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def test_saldo_bloqueio_individual_traz_acao_sugerida(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "100"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["disponivel"] is False
    assert data["individual"]["acao_sugerida"] == "solicitar_recurso_extra"


def test_saldo_bloqueio_territorial_traz_acao_sugerida(
    auth_client_solicitante, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("100"), valor_comprometido=Decimal("100"),
    )
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "50"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["territorial"]["disponivel"] is False
    assert data["territorial"]["acao_sugerida"] == "acionar_articulador"


def test_saldo_disponivel_traz_semaforo(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["semaforo"] in {"verde", "amarelo", "vermelho"}
    assert data["territorial"]["semaforo"] in {"verde", "amarelo", "vermelho"}
    assert data["individual"]["acao_sugerida"] is None
    assert data["territorial"]["acao_sugerida"] is None
