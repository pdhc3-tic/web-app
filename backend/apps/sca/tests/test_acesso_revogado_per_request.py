"""
Invalidação imediata da sessão ativa após revogação de acesso.

Um usuário com `acesso_revogado=True` é rejeitado com 401 em TODA view
autenticada (SCA e views genéricas do core), mesmo com access token JWT
ainda válido — a checagem é feita por request no permission layer
(`IsAuthenticatedActiveAccess`), sem depender do blacklist de refresh tokens.
"""

import pytest


@pytest.fixture
def auth_client_revogado(auth_client, usuario):
    usuario.acesso_revogado = True
    usuario.save(update_fields=["acesso_revogado"])
    return auth_client


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("post", "/api/v1/sca/sync/push/", {"data": {}, "format": "json"}),
        ("get", "/api/v1/sca/sync/pull/", {"format": "json"}),
        ("get", "/api/v1/sca/sync/forms/", {"format": "json"}),
        ("get", "/api/v1/sca/sync/status/", {"format": "json"}),
        ("get", "/api/v1/auth/me/", {"format": "json"}),
        ("get", "/api/v1/notifications/me/", {"format": "json"}),
    ],
)
def test_acesso_revogado_rejeita_todas_as_views_com_401(auth_client_revogado, method, path, kwargs):
    response = getattr(auth_client_revogado, method)(path, **kwargs)

    assert response.status_code == 401
    assert "Acesso revogado" in response.data["detail"]


@pytest.mark.django_db
def test_acesso_vigente_funciona_normalmente(auth_client):
    response = auth_client.get("/api/v1/sca/sync/status/", format="json")

    assert response.status_code == 200
    assert response.data["acesso_revogado"] is False


@pytest.mark.django_db
def test_reativacao_permite_requests_novamente(auth_client, usuario):
    usuario.acesso_revogado = True
    usuario.save(update_fields=["acesso_revogado"])
    assert auth_client.get("/api/v1/sca/sync/status/", format="json").status_code == 401

    usuario.acesso_revogado = False
    usuario.save(update_fields=["acesso_revogado"])

    response = auth_client.get("/api/v1/sca/sync/status/", format="json")
    assert response.status_code == 200
