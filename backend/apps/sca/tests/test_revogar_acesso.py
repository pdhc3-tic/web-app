"""
Testes do fluxo de revogação/reativação de acesso.

PATCH /api/v1/users/{id}/revogar-acesso/ e /reativar-acesso/ —
blacklista todos os refresh tokens do usuário e atualiza a flag.
"""

import pytest
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.tests.factories import UserFactory


@pytest.mark.django_db
def test_revogar_acesso_blacklista_tokens(auth_client_super_admin):
    alvo = UserFactory(email="alvo@test.com", nome="Alvo")

    tokens = []
    for _ in range(3):
        tokens.append(RefreshToken.for_user(alvo))
    assert OutstandingToken.objects.filter(user=alvo).count() == 3

    response = auth_client_super_admin.patch(
        f"/api/v1/users/{alvo.pk}/revogar-acesso/",
        format="json",
    )

    assert response.status_code == 200
    assert response.data["acesso_revogado"] is True
    alvo.refresh_from_db()
    assert alvo.acesso_revogado is True
    assert alvo.acesso_revogado_por is not None
    assert BlacklistedToken.objects.filter(token__user=alvo).count() == 3


@pytest.mark.django_db
def test_reativar_acesso_limpa_flag(auth_client_super_admin):
    alvo = UserFactory(email="alvo2@test.com", nome="Alvo 2")
    alvo.acesso_revogado = True
    alvo.save(update_fields=["acesso_revogado"])

    response = auth_client_super_admin.patch(
        f"/api/v1/users/{alvo.pk}/reativar-acesso/",
        format="json",
    )

    assert response.status_code == 200
    assert response.data["acesso_revogado"] is False
    alvo.refresh_from_db()
    assert alvo.acesso_revogado is False
    assert alvo.acesso_revogado_em is None
    assert alvo.acesso_revogado_por is None


@pytest.mark.django_db
def test_revogar_acesso_exige_super_admin(api_client, usuario):
    alvo = UserFactory(email="alvo3@test.com", nome="Alvo 3")
    api_client.force_authenticate(user=usuario)

    response = api_client.patch(
        f"/api/v1/users/{alvo.pk}/revogar-acesso/",
        format="json",
    )

    assert response.status_code == 403
    alvo.refresh_from_db()
    assert alvo.acesso_revogado is False


@pytest.mark.django_db
def test_reativacao_exige_novo_login_tokens_antigos_invalidos(auth_client_super_admin):
    alvo = UserFactory(email="alvo4@test.com", nome="Alvo 4")
    token_antigo = str(RefreshToken.for_user(alvo))

    assert auth_client_super_admin.patch(
        f"/api/v1/users/{alvo.pk}/revogar-acesso/", format="json"
    ).status_code == 200
    assert auth_client_super_admin.patch(
        f"/api/v1/users/{alvo.pk}/reativar-acesso/", format="json"
    ).status_code == 200

    alvo.refresh_from_db()
    assert alvo.acesso_revogado is False

    # Token antigo (emitido antes da revogação) continua blacklisted → novo login obrigatório.
    response = auth_client_super_admin.post(
        "/api/v1/sca/auth/refresh/",
        data={"refresh_token": token_antigo},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["code"] == "INVALID_REFRESH_TOKEN"
