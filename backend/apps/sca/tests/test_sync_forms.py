"""
Testes do endpoint GET /api/v1/sca/sync/forms/.

Fail-safe: mesmo sem formulários SGF disponíveis, retorna lista vazia 200.
"""

import pytest


def get_forms(auth_client, since=None):
    params = {}
    if since is not None:
        params["since"] = since.isoformat()
    return auth_client.get("/api/v1/sca/sync/forms/", data=params, format="json")


@pytest.mark.django_db
def test_forms_sem_sgf_disponivel_retorna_200_lista_vazia(auth_client):
    response = get_forms(auth_client)

    assert response.status_code == 200
    assert response.data["formularios"] == []
    assert response.data["server_time"]
