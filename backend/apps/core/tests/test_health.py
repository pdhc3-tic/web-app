"""Rota de health usada pelo healthcheck do compose e pelo deploy."""
import pytest


@pytest.mark.django_db
def test_health_toca_o_banco(client):
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
