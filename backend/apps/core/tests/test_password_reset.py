import pytest
import hashlib
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient
from apps.core.tests.factories import UserFactory
from apps.core.models.password_reset_token import PasswordResetToken
from apps.core.models.audit_log import AuditLog
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

# O LocMemCache persiste entre testes no mesmo processo.
# Sem limpeza, um teste "contamina" o outro. 
# Por isso foi criado essa fixture para limpar o cache.
@pytest.fixture(autouse=False)
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

###############################################
##  testes endpoint password-reset/request/  ##
###############################################
@pytest.mark.django_db
def test_request_retorna_202_email_valido(client, usuario):
    with patch("setup.views.send_email_notification.delay"):
        response = client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    assert response.status_code == 202
    assert response.data["message"] == "Se o e-mail estiver cadastrado, um link foi enviado."

@pytest.mark.django_db
def test_request_retorna_202_email_inexistente(client):
    response = client.post("/api/v1/auth/password-reset/request/", {
        "email": "naoexiste@example.com",
    })
    assert response.status_code == 202
    assert response.data["message"] == "Se o e-mail estiver cadastrado, um link foi enviado."

@pytest.mark.django_db
def test_request_nao_envia_email_usuario_inativo(client):
    usuario = UserFactory(ativo=False)
    with patch("setup.views.send_email_notification.delay") as mock_send:
        client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    mock_send.assert_not_called()

@pytest.mark.django_db
def test_request_envia_email_usuario_ativo(client, usuario):
    with patch("setup.views.send_email_notification.delay") as mock_send:
        client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    mock_send.assert_called_once()

################################################
##  testes endpoint /password-reset/confirm/  ##
################################################
@pytest.mark.django_db
def test_confirm_retorna_200_token_valido(client, usuario):
    refresh = RefreshToken.for_user(usuario)
    token_raw = "token-valido-teste-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 200
    assert response.data["message"] == "Senha redefinida com sucesso."

@pytest.mark.django_db
def test_confirm_token_invalido(client, limpa_cache):
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": "token-inexistente",
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 400
    assert response.data["code"] == ["INVALID_TOKEN"]

@pytest.mark.django_db
def test_confirm_token_ja_usado(client, usuario, limpa_cache):
    token_raw = "token-ja-usado-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
        used_at=timezone.now(),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 400
    assert response.data["code"] == ["INVALID_TOKEN"]

@pytest.mark.django_db
def test_confirm_token_expirado(client, usuario, limpa_cache):
    token_raw = "token-expirado-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "NovaSenha123",
    })
    assert response.status_code == 400
    assert response.data["code"] == ["EXPIRED_TOKEN"]

@pytest.mark.django_db
def test_confirm_senha_fraca_curta(client, usuario, limpa_cache):
    token_raw = "token-senha-fraca-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "Abc1",
    })
    assert response.status_code == 400

@pytest.mark.django_db
def test_confirm_senha_sem_maiuscula(client, usuario, limpa_cache):
    token_raw = "token-sem-maiuscula-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "1234567890",
    })
    assert response.status_code == 400

@pytest.mark.django_db
def test_confirm_senha_sem_numero(client, usuario, limpa_cache):
    token_raw = "token-sem-numero-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    response = client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "SenhaSemNumero",
    })
    assert response.status_code == 400

@pytest.mark.django_db
def test_confirm_revoga_refresh_tokens(client, usuario, limpa_cache):
    refresh1 = RefreshToken.for_user(usuario)
    refresh2 = RefreshToken.for_user(usuario)
    token_raw = "token-revoga-refresh-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "NovaSenha123",
    })
    response1 = client.post("/api/v1/auth/token/refresh/", {"refresh_token": str(refresh1)})
    response2 = client.post("/api/v1/auth/token/refresh/", {"refresh_token": str(refresh2)})
    assert response1.status_code == 401
    assert response2.status_code == 401

@pytest.mark.django_db
def test_confirm_registra_audit_log(client, usuario, limpa_cache):
    token_raw = "token-audit-log-123"
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=usuario,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    client.post("/api/v1/auth/password-reset/confirm/", {
        "token": token_raw,
        "nova_senha": "NovaSenha123",
    })
    assert AuditLog.objects.filter(usuario=usuario, evento="password_reset").exists()

################################################
##  testes throttles                          ##
################################################
@pytest.mark.django_db
def test_throttle_por_email(client, usuario, limpa_cache):
    with patch("setup.views.send_email_notification.delay"):
        for _ in range(3):
            response = client.post("/api/v1/auth/password-reset/request/", {
                "email": usuario.email,
            })
        assert response.status_code == 202

        response = client.post("/api/v1/auth/password-reset/request/", {
            "email": usuario.email,
        })
    assert response.status_code == 429

@pytest.mark.django_db
def test_throttle_por_ip(client, limpa_cache):
    # client.defaults["REMOTE_ADDR"] = "10.0.0.1" PARA FIXAR O IP, SEM ISSO
    # O APIClient usa IPs diferentes a cada request em aguns ambientes. 
    # Emails diferentes em cada iteração garantem que o throttle de email
    # não seja acionado antes do IP.
    client.defaults["REMOTE_ADDR"] = "10.0.0.1"
    with patch("setup.views.send_email_notification.delay"):
        for i in range(5):
            response = client.post("/api/v1/auth/password-reset/request/", {
                "email": f"diferente{i}@example.com",
            })
        assert response.status_code == 202

        response = client.post("/api/v1/auth/password-reset/request/", {
            "email": "sexta@example.com",
        })
    assert response.status_code == 429