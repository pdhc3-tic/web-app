"""
Testes do endpoint POST /api/v1/sca/auth/refresh/.

Refresh do token de sessão do SCA: rotação, validação, acesso revogado,
sessão expirada por inatividade e expiração do refresh token.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.sca.models import SyncDevice, SyncEvent


def do_refresh(api_client, refresh_token, device_id="dev-001"):
    return api_client.post(
        "/api/v1/sca/auth/refresh/",
        data={"refresh_token": str(refresh_token)},
        HTTP_X_DEVICE_ID=device_id,
        format="json",
    )


@pytest.mark.django_db
def test_refresh_valido_retorna_novos_tokens_e_rotaciona(api_client, usuario):
    refresh = RefreshToken.for_user(usuario)
    original = str(refresh)

    response = do_refresh(api_client, refresh)

    assert response.status_code == 200
    assert response.data["access_token"]
    assert response.data["refresh_token"]
    assert response.data["refresh_token"] != original
    assert SyncEvent.objects.filter(user=usuario, tipo=SyncEvent.Tipo.REFRESH).exists()


@pytest.mark.django_db
def test_refresh_invalido_retorna_401(api_client):
    response = do_refresh(api_client, "token-invalido")

    assert response.status_code == 401
    assert response.data["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_com_acesso_revogado_retorna_401(api_client, usuario):
    usuario.acesso_revogado = True
    usuario.save(update_fields=["acesso_revogado"])
    refresh = RefreshToken.for_user(usuario)

    response = do_refresh(api_client, refresh)

    assert response.status_code == 401
    assert response.data["code"] == "ACCESS_REVOKED"


@pytest.mark.django_db
def test_refresh_registra_device(api_client, usuario):
    refresh = RefreshToken.for_user(usuario)

    do_refresh(api_client, refresh, device_id="dev-scda-1")

    assert SyncDevice.objects.filter(user=usuario, device_id="dev-scda-1").exists()


@pytest.mark.django_db
def test_refresh_sessao_expirada_por_inatividade_retorna_401(api_client, usuario):
    evento = SyncEvent.objects.create(
        user=usuario,
        device=None,
        tipo=SyncEvent.Tipo.PUSH,
        contagem=0,
    )
    SyncEvent.objects.filter(pk=evento.pk).update(
        recebido_em=timezone.now() - timedelta(days=31)
    )
    refresh = RefreshToken.for_user(usuario)

    response = do_refresh(api_client, refresh)

    assert response.status_code == 401
    assert response.data["code"] == "SESSION_EXPIRED"


@pytest.mark.django_db
def test_refresh_apos_sync_recente_nao_experia(api_client, usuario):
    evento = SyncEvent.objects.create(
        user=usuario,
        device=None,
        tipo=SyncEvent.Tipo.PUSH,
        contagem=1,
    )
    SyncEvent.objects.filter(pk=evento.pk).update(
        recebido_em=timezone.now() - timedelta(days=5)
    )
    refresh = RefreshToken.for_user(usuario)

    response = do_refresh(api_client, refresh)

    assert response.status_code == 200
