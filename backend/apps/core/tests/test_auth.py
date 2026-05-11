import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.settings import api_settings
from unittest.mock import patch
from setup.tasks import cleanup_expired_tokens

from apps.core.tests.factories import UserFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    return UserFactory()

# Testes referentes ao endpoint login
@pytest.mark.django_db
def test_login_valido(client, usuario):
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200
    assert "access_token" in response.data
    assert "refresh_token" in response.data

@pytest.mark.django_db
def test_login_senha_errada(client, usuario):
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })
    assert response.status_code == 401
    assert response.data["detail"] == "Usuário e/ou senha incorreto(s)"

@pytest.mark.django_db
def test_login_email_inexistente(client):
    response = client.post("/api/v1/auth/login/", {
        "email": "naoexiste@example.com",
        "senha": "senha123",
    })
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_usuario_inativo(client):
    usuario = UserFactory(is_active=False)
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 401

# Testes de Payload inválido
@pytest.mark.django_db
def test_login_sem_email(client):
    response = client.post("/api/v1/auth/login/", {
        "senha": "senha123",
    })
    assert response.status_code == 400

@pytest.mark.django_db
def test_login_sem_senha(client):
    response = client.post("/api/v1/auth/login/", {
        "email": "qualquer@example.com",
    })
    assert response.status_code == 400

@pytest.mark.django_db
def test_login_body_vazio(client):
    response = client.post("/api/v1/auth/login/", {})
    assert response.status_code == 400

@pytest.mark.django_db
def test_login_campos_resposta(client, usuario):
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200
    assert "access_token" in response.data
    assert "refresh_token" in response.data
    assert "access" not in response.data
    assert "refresh" not in response.data

# ######################################
# Teste para Token expirado
# ######################################
@pytest.mark.django_db
def test_token_expirado(client, usuario):
    refresh = RefreshToken.for_user(usuario)
    access_token = refresh.access_token

    access_token.set_exp(
        from_time=(timezone.localtime() - timedelta(hours=8))
    )
    response = client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {(access_token)}")

    assert response.status_code == 401

# ######################################
# Testes referentes ao endpoint refresh
# ######################################
@pytest.mark.django_db
def test_refresh_valido(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200
    assert "access_token" in response.data
    assert "refresh_token" in response.data
    assert "access" not in response.data
    assert "refresh" not in response.data

@pytest.mark.django_db
def test_refresh_token_invalido(client):
    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": "token-invalido-qualquer",
    })
    assert response.status_code == 401

@pytest.mark.django_db
def test_refresh_token_rotacionado(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    # Usa o refresh token uma vez — ele é rotacionado e invalidado
    client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })

    # Tenta usar o mesmo refresh token antigo
    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 401

@pytest.mark.django_db
def test_refresh_token_apos_logout(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    client.post("/api/v1/auth/logout/", {
        "refresh_token": str(refresh),
    })

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 401

@pytest.mark.django_db
def test_refresh_sem_token(client):
    response = client.post("/api/v1/auth/token/refresh/", {})
    assert response.status_code == 400

@pytest.mark.django_db
def test_refresh_body_vazio(client):
    response = client.post("/api/v1/auth/token/refresh/")
    assert response.status_code == 400

# ######################################
# Testes referentes ao endpoint logout
# ######################################

@pytest.mark.django_db
def test_logout_valido(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    response = client.post("/api/v1/auth/logout/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200
    assert response.data == {}

@pytest.mark.django_db
def test_logout_invalida_refresh_token(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    reponseLogout = client.post("/api/v1/auth/logout/", {
        "refresh_token": str(refresh),
    })

    responseRefresh = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert reponseLogout.status_code == 200
    assert responseRefresh.status_code == 401

@pytest.mark.django_db
def test_logout_all(client, usuario):
    # Simula dois logins em dispositivos diferentes
    login1 = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    login2 = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })

    access_token = login1.data["access_token"]
    refresh1     = login1.data["refresh_token"]
    refresh2     = login2.data["refresh_token"]

    # Chama o logout-all com o access token no header
    response = client.post(
        "/api/v1/auth/logout-all/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}"
    )
    assert response.status_code == 200

    # Confirma que todos os refresh tokens foram invalidados
    response1 = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh1),
    })
    response2 = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh2),
    })
    assert response1.status_code == 401
    assert response2.status_code == 401

@pytest.mark.django_db
def test_cleanup_expired_tokens():
    with patch("setup.tasks.call_command") as mock_call_command:
        cleanup_expired_tokens()
        mock_call_command.assert_called_once_with("flushexpiredtokens")