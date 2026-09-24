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
    # Sem limite configurado a orientação é a mesma da trava individual
    # esgotada — não "procure o Super Admin".
    assert "Solicitar recurso extra" in data["individual"]["motivo_bloqueio"]


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
    assert "acione o Articulador Estadual" in data["territorial"]["motivo_bloqueio"]


def test_saldo_disponivel_traz_semaforo(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["semaforo_atual"] == "verde"
    assert data["individual"]["semaforo_apos"] == "verde"
    assert data["territorial"]["semaforo_atual"] == "verde"
    assert data["territorial"]["semaforo_apos"] == "verde"
    assert data["individual"]["acao_sugerida"] is None
    assert data["territorial"]["acao_sugerida"] is None
    assert data["individual"]["motivo_bloqueio"] is None
    assert data["territorial"]["motivo_bloqueio"] is None


def test_saldo_semaforo_apos_mostra_mudanca_de_faixa(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    # Limite individual de 5.000: 3.600 leva de 0% a 72% (cruza 70%). Pool
    # territorial de 10.000: os mesmos 3.600 dão 36%, continua verde.
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "3600"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["disponivel"] is True
    assert data["individual"]["semaforo_atual"] == "verde"
    assert data["individual"]["semaforo_apos"] == "amarelo"
    assert data["territorial"]["semaforo_atual"] == "verde"
    assert data["territorial"]["semaforo_apos"] == "verde"


def test_saldo_semaforo_segue_limiares_configurados_no_core(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="budget_alert_yellow_pct", defaults={"valor": "30", "tipo": TipoConfiguracao.INTEGER},
    )
    try:
        response = auth_client_solicitante.get(
            "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "3600"},
        )
        assert response.status_code == 200
        assert response.json()["territorial"]["semaforo_apos"] == "amarelo"
    finally:
        # Cache de SystemConfig não é transacional — limpa pra não vazar
        # o limiar de 30% pros testes seguintes.
        cache.delete("system_config:budget_alert_yellow_pct")


def test_saldo_limite_individual_insuficiente_orienta_recurso_extra(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "6000"},
    )
    assert response.status_code == 200
    individual = response.json()["individual"]
    assert individual["disponivel"] is False
    assert "R$ 5000" in individual["motivo_bloqueio"]
    assert "Solicitar recurso extra" in individual["motivo_bloqueio"]
