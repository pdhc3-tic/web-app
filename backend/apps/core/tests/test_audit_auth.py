import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models.audit_log import AuditLog
from apps.core.models.login_attempt import LoginAttempt
from apps.core.tests.factories import UserFactory


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


@pytest.mark.django_db
def test_login_success_registra_audit_log_sem_tokens(client, usuario):
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })

    assert response.status_code == 200
    log = AuditLog.objects.filter(
        user=usuario,
        acao="auth.login_success",
        entidade="User",
        entidade_id=str(usuario.pk),
    ).last()
    assert log is not None
    assert log.valores_novos == {"status": "success"}
    assert "access_token" not in log.valores_novos
    assert "refresh_token" not in log.valores_novos


@pytest.mark.django_db
def test_login_failed_registra_audit_log(client, usuario):
    response = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha-errada",
    })

    assert response.status_code == 401
    log = AuditLog.objects.filter(
        user=usuario,
        acao="auth.login_failed",
        entidade="User",
        entidade_id=str(usuario.pk),
    ).last()
    assert log is not None
    assert log.valores_novos["reason"] == LoginAttempt.MotivFalha.INVALID_CREDENTIALS


@pytest.mark.django_db
def test_login_rate_limited_registra_audit_log(client, usuario):
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
    log = AuditLog.objects.filter(
        user=usuario,
        acao="auth.login_rate_limited",
        entidade="User",
        entidade_id=str(usuario.pk),
    ).last()
    assert log is not None
    assert log.valores_novos["reason"] == LoginAttempt.MotivFalha.RATE_LIMITED


@pytest.mark.django_db
def test_logout_registra_audit_log_por_refresh_token(client, usuario):
    refresh = RefreshToken.for_user(usuario)

    response = client.post("/api/v1/auth/logout/", {
        "refresh_token": str(refresh),
    })

    assert response.status_code == 200
    assert AuditLog.objects.filter(
        user=usuario,
        acao="auth.logout_success",
        entidade="User",
        entidade_id=str(usuario.pk),
    ).exists()


@pytest.mark.django_db
def test_logout_all_registra_audit_log(client, usuario):
    login = client.post("/api/v1/auth/login/", {
        "email": usuario.email,
        "senha": "senha123",
    })

    response = client.post(
        "/api/v1/auth/logout-all/",
        HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}",
    )

    assert response.status_code == 200
    log = AuditLog.objects.filter(
        user=usuario,
        acao="auth.logout_all_success",
        entidade="User",
        entidade_id=str(usuario.pk),
    ).last()
    assert log is not None
    assert log.valores_novos["revoked_count"] >= 1
