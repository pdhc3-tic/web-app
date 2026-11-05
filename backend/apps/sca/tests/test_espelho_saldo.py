"""Espelho de saldo: a fotografia de "meu saldo" gravada no último pull."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.sca.models import SyncDevice
from apps.sgp.models import SpendingLimit
from apps.sgp.tests.factories import BudgetRubricaFactory, SpendingLimitFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sca/saldo/"
PULL_URL = "/api/v1/sca/sync/pull/"
MEU_SALDO_URL = "/api/v1/sgp/orcamento/meu-saldo/"


def _pull(cliente, device_id="dev-001"):
    resposta = cliente.get(PULL_URL, HTTP_X_DEVICE_ID=device_id)
    assert resposta.status_code == 200
    return resposta


@pytest.fixture
def limite(usuario):
    return SpendingLimitFactory(
        user=usuario, rubrica=BudgetRubricaFactory(), valor_limite=1000, valor_comprometido=200,
    )


def test_espelho_bate_com_meu_saldo_no_momento_do_sync(auth_client, limite):
    _pull(auth_client)

    resposta = auth_client.get(URL, HTTP_X_DEVICE_ID="dev-001")

    assert resposta.status_code == 200
    assert resposta.json()["saldos"] == auth_client.get(MEU_SALDO_URL).json()
    assert resposta.json()["saldos"][0]["disponivel"] == "800.00"


def test_ultimo_sync_e_o_ultimo_pull_do_dispositivo(auth_client, usuario, limite):
    _pull(auth_client)

    resposta = auth_client.get(URL, HTTP_X_DEVICE_ID="dev-001").json()

    dispositivo = SyncDevice.objects.get(user=usuario, device_id="dev-001")
    assert resposta["ultimo_sync"] == dispositivo.ultimo_pull_em.isoformat()


def test_movimentacao_depois_do_sync_so_aparece_no_proximo_pull(auth_client, limite):
    _pull(auth_client)
    SpendingLimit.objects.filter(pk=limite.pk).update(valor_comprometido=Decimal("700"))

    defasado = auth_client.get(URL, HTTP_X_DEVICE_ID="dev-001").json()
    _pull(auth_client)
    atualizado = auth_client.get(URL, HTTP_X_DEVICE_ID="dev-001").json()

    assert defasado["saldos"][0]["disponivel"] == "800.00"
    assert atualizado["saldos"][0]["disponivel"] == "300.00"


def test_pull_de_usuario_sem_territorio_tambem_grava_o_espelho(auth_client, usuario, limite):
    usuario.profiles.all().delete()

    _pull(auth_client)

    dispositivo = SyncDevice.objects.get(user=usuario, device_id="dev-001")
    assert dispositivo.espelho_saldo[0]["rubrica"] == limite.rubrica.slug


def test_sem_device_id_vale_o_pull_mais_recente_do_usuario(auth_client, usuario, limite):
    _pull(auth_client, "dev-antigo")
    SyncDevice.objects.filter(user=usuario, device_id="dev-antigo").update(
        ultimo_pull_em=timezone.now() - timedelta(days=2), espelho_saldo=[{"rubrica": "antiga"}],
    )
    _pull(auth_client, "dev-novo")

    resposta = auth_client.get(URL).json()

    assert resposta["saldos"][0]["rubrica"] == limite.rubrica.slug


def test_nunca_sincronizou_vem_vazio_e_nao_cria_dispositivo(auth_client, usuario):
    resposta = auth_client.get(URL, HTTP_X_DEVICE_ID="dev-novo")

    assert resposta.status_code == 200
    assert resposta.json() == {"saldos": [], "ultimo_sync": None}
    assert not SyncDevice.objects.filter(user=usuario, device_id="dev-novo").exists()


def test_nao_devolve_o_espelho_de_outro_usuario(auth_client, auth_client_super_admin, limite):
    _pull(auth_client)

    resposta = auth_client_super_admin.get(URL, HTTP_X_DEVICE_ID="dev-001").json()

    assert resposta == {"saldos": [], "ultimo_sync": None}


def test_rota_e_somente_leitura(auth_client):
    assert auth_client.post(URL, {}, format="json").status_code == 405


def test_exige_autenticacao(client):
    assert client.get(URL).status_code == 401
