import pytest
from rest_framework.test import APIClient
from unittest.mock import patch
from django.core.cache import cache
from apps.core.tests.factories import UserFactory
from apps.core.models.login_attempt import LoginAttempt
from apps.core.throttling import (
    LoginRateThrottle,
    PasswordResetByEmailThrottle,
    PasswordResetByIPThrottle,
    PasswordResetConfirmThrottle,
    RefreshRateThrottle,
)
from rest_framework_simplejwt.tokens import RefreshToken
from apps.core.views.auth import LoginView, RefreshView, password_reset_confirm, password_reset_request


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


def test_custom_window_rate_throttle_parseia_janela_de_5_minutos():
    throttle = PasswordResetByEmailThrottle()

    assert throttle.parse_rate("5/5min") == (5, 300)
    assert throttle.parse_rate("10/5min") == (10, 300)
    assert throttle.parse_rate("3/5min") == (3, 300)


def test_custom_window_rate_throttle_parseia_janela_em_horas():
    throttle = PasswordResetByEmailThrottle()

    assert throttle.parse_rate("3/hour") == (3, 3600)
    assert throttle.parse_rate("5/hour") == (5, 3600)
    assert throttle.parse_rate("1/hours") == (1, 3600)


def test_password_reset_email_throttle_normaliza_email():
    request = type("Request", (), {"data": {"email": " Usuario@Example.COM "}})()

    cache_key = PasswordResetByEmailThrottle().get_cache_key(request, None)

    assert cache_key == "throttle_auth_password_reset_email_usuario@example.com"


def test_views_usam_throttles_independentes():
    assert LoginView.throttle_classes == [LoginRateThrottle]
    assert RefreshView.throttle_classes == [RefreshRateThrottle]
    assert password_reset_request.cls.throttle_classes == [
        PasswordResetByIPThrottle,
        PasswordResetByEmailThrottle,
    ]
    assert password_reset_confirm.cls.throttle_classes == [PasswordResetConfirmThrottle]


##########################################################
## LoginRateThrottle — limite de 5/5min por IP no login ##
##########################################################

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

    for _ in range(10):
        client.post("/api/v1/auth/token/refresh/", {
            "refresh_token": "token-invalido",
        })

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 429


@pytest.mark.django_db
def test_refresh_throttle_nao_bloqueia_login(client, usuario):
    for _ in range(10):
        client.post("/api/v1/auth/token/refresh/", {
            "refresh_token": "token-invalido",
        })

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_throttle_nao_bloqueia_refresh(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_throttle_nao_bloqueia_password_reset_request(client, usuario):
    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    with patch("apps.core.views.auth.send_email_notification.delay"):
        response = client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    assert response.status_code == 202


@pytest.mark.django_db
def test_login_throttle_nao_bloqueia_password_reset_confirm(client, usuario):
    for _ in range(5):
        client.post("/api/v1/auth/login/", {
            "email": usuario.email,
            "senha": "senha-errada",
        })

    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": "token-inexistente",
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 400


@pytest.mark.django_db
def test_password_reset_request_throttle_por_email_nao_bloqueia_login_e_refresh(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    with patch("apps.core.views.auth.send_email_notification.delay"):
        for _ in range(3):
            response = client.post("/api/v1/auth/password-reset/request/", {
                "email": usuario.email,
            })
            assert response.status_code == 202

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_password_reset_request_throttle_por_ip_nao_bloqueia_login_e_refresh(client, usuario):
    refresh = RefreshToken.for_user(usuario)
    client.defaults["REMOTE_ADDR"] = "10.0.0.1"

    with patch("apps.core.views.auth.send_email_notification.delay"):
        for i in range(5):
            response = client.post("/api/v1/auth/password-reset/request/", {
                "email": f"diferente{i}@example.com",
            })
            assert response.status_code == 202

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_password_reset_confirm_throttle_nao_bloqueia_login_e_refresh(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    for _ in range(3):
        response = client.post("/api/v1/auth/password-reset/confirm/", {
            "token": "token-inexistente",
            "nova_senha": "NovaSenha123",
        })
        assert response.status_code == 400

    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })
    assert response.status_code == 200

    response = client.post("/api/v1/auth/token/refresh/", {
        "refresh_token": str(refresh),
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_refresh_throttle_nao_bloqueia_password_reset_request_e_confirm(client, usuario):
    for _ in range(10):
        client.post("/api/v1/auth/token/refresh/", {
            "refresh_token": "token-invalido",
        })

    with patch("apps.core.views.auth.send_email_notification.delay"):
        response = client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    assert response.status_code == 202

    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": "token-inexistente",
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 400


@pytest.mark.django_db
def test_password_reset_confirm_throttle_bloqueia_apos_limite(client):
    for _ in range(3):
        response = client.post("/api/v1/auth/password-reset/confirm/", {
            "token": "token-inexistente",
            "nova_senha": "NovaSenha123",
        })
        assert response.status_code == 400

    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": "token-inexistente",
        "nova_senha": "NovaSenha123",
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

def test_custom_window_rate_throttle_gera_cache_key_por_ip():
    request = type("request", (), {"META": {"REMOTE_ADDR": "127.0.0.1"}})()
    cache_key = LoginRateThrottle().get_cache_key(request, None)

    assert cache_key == "throttle_auth_login_127.0.0.1" 
