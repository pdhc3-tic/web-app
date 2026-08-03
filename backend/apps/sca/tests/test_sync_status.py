"""
Testes do endpoint GET /api/v1/sca/sync/status/.

Status do sync: último sync no servidor, registros pendentes para o device
e flag de acesso revogado.
"""

from datetime import timedelta
import time

import pytest
from django.utils import timezone

from apps.sca.models import SyncDevice
from apps.sgp.tests.factories import UPFFactory


def get_status(auth_client, device_id="dev-001"):
    return auth_client.get(
        "/api/v1/sca/sync/status/",
        HTTP_X_DEVICE_ID=device_id,
        format="json",
    )


@pytest.mark.django_db
def test_status_sem_device_retorna_none_e_zero(auth_client, usuario):
    response = get_status(auth_client)

    assert response.status_code == 200
    assert response.data["ultimo_sync_servidor"] is None
    assert response.data["registros_pendentes_servidor"] == 0
    assert response.data["acesso_revogado"] is False


@pytest.mark.django_db
def test_status_com_ultimo_sync_e_pendentes(auth_client, usuario, municipio, projeto):
    device = SyncDevice.objects.create(user=usuario, device_id="dev-001")
    device.ultimo_push_em = timezone.now() - timedelta(hours=2)
    device.save(update_fields=["ultimo_push_em"])

    UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")

    response = get_status(auth_client)

    assert response.status_code == 200
    assert response.data["ultimo_sync_servidor"] is not None
    assert response.data["registros_pendentes_servidor"] == 2  # 1 UPF + 1 membro (titular)
    assert response.data["acesso_revogado"] is False


@pytest.mark.django_db
def test_status_acesso_revogado(auth_client, usuario):
    usuario.acesso_revogado = True
    usuario.save(update_fields=["acesso_revogado"])

    response = get_status(auth_client)

    assert response.status_code == 200
    assert response.data["acesso_revogado"] is True


@pytest.mark.django_db
def test_status_nao_duplica_device(auth_client, usuario):
    get_status(auth_client)
    get_status(auth_client)

    assert SyncDevice.objects.filter(user=usuario, device_id="dev-001").count() == 1


@pytest.mark.django_db
def test_status_performance_abaixo_200ms(auth_client, usuario, municipio, projeto):
    for i in range(500):
        UPFFactory(
            municipio=municipio,
            projeto=projeto,
            titular_cpf=f"{i:011d}",
        )

    inicio = time.perf_counter()
    response = get_status(auth_client)
    duracao_ms = (time.perf_counter() - inicio) * 1000

    assert response.status_code == 200
    assert response.data["registros_pendentes_servidor"] == 1000  # 500 UPFs + 500 titulares
    assert duracao_ms < 200, f"Status demorou {duracao_ms:.1f}ms (limite: 200ms)"
