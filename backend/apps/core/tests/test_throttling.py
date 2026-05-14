import pytest
from rest_framework.test import APIClient
from unittest.mock import patch
from django.core.cache import cache
from apps.core.tests.factories import UserFactory
from apps.core.models.login_attempt import LoginAttempt
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture(autouse=True)
def limpa_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    return UserFactory()


#########################################################
## LoginRateThrottle — limite de 5/min por IP no login ##
#########################################################

@pytest.mark.django_db
def test_login_throttle_bloqueia_apos_limite(client, usuario):
    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })
    assert response.status_code == 429

@pytest.mark.django_db
def test_login_throttle_resposta_padronizada(client, usuario):
    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })
    assert response.status_code == 429
    assert response.data["code"] == "THROTTLED"
    assert "message" in response.data
    assert "retry_after" in response.data
    assert "Retry-After" in response

@pytest.mark.django_db
def test_refresh_throttle_bloqueia_apos_limite(client, usuario):    
    refresh = RefreshToken.for_user(usuario)

    for _ in range(5):
        client.post("/api/v1/auth/token/refresh/", {
            "refresh_token": "token-invalido",
        })

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 429

############################################
## LoginAttempt — gravação de tentativas  ##
############################################

@pytest.mark.django_db
def test_login_attempt_sucesso(client, usuario):
    client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    tentativa = LoginAttempt.objects.get(email=usuario.email)
    assert tentativa.sucesso is True
    assert tentativa.motivo_falha is None

@pytest.mark.django_db
def test_login_attempt_credenciais_invalidas(client, usuario):
    client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })
    tentativa = LoginAttempt.objects.get(email=usuario.email)
    assert tentativa.sucesso is False
    assert tentativa.motivo_falha == LoginAttempt.MotivFalha.INVALID_CREDENTIALS

@pytest.mark.django_db
def test_login_attempt_usuario_inativo(client):
    usuario = UserFactory(ativo=False)
    client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    tentativa = LoginAttempt.objects.get(email=usuario.email)
    assert tentativa.sucesso is False
    assert tentativa.motivo_falha == LoginAttempt.MotivFalha.INACTIVE_USER

@pytest.mark.django_db
def test_login_attempt_formato_invalido(client):
    client.post("/api/v1/auth/login/", {
        "email": "nao-e-um-email",
        "senha": "senha123",
    })
    tentativa = LoginAttempt.objects.filter(email="nao-e-um-email").first()
    assert tentativa is not None
    assert tentativa.sucesso is False
    assert tentativa.motivo_falha == LoginAttempt.MotivFalha.INVALID_FORMAT

@pytest.mark.django_db
def test_login_attempt_rate_limited(client, usuario):
    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })

    tentativas = LoginAttempt.objects.filter(
        email=usuario.email,
        motivo_falha=LoginAttempt.MotivFalha.RATE_LIMITED
    )
    assert tentativas.exists()

@pytest.mark.django_db
def test_login_attempt_grava_ip(client, usuario):
    client.defaults["REMOTE_ADDR"] = "192.168.1.1"
    client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    tentativa = LoginAttempt.objects.get(email=usuario.email)
    assert tentativa.ip == "192.168.1.1"

###############################################
## X-Forwarded-For — IP real atrás de proxy  ##
###############################################

@pytest.mark.django_db
def test_login_attempt_ip_via_forwarded_for(client, usuario):
    client.post(
        "/api/v1/auth/login/",
        {"email": usuario.email, "senha": "senha123"},
        HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1",
    )
    tentativa = LoginAttempt.objects.get(email=usuario.email)
    assert tentativa.ip == "203.0.113.5"