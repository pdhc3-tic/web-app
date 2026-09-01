from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.models.power_bi_token import PowerBIToken
from apps.sgp.cache import set_power_bi_snapshot


pytestmark = pytest.mark.django_db

STATUS_URL = "/api/v1/admin/power-bi-token/"
REGENERATE_URL = "/api/v1/admin/power-bi-token/regenerar/"
POWER_BI_URL = "/api/v1/sgp/plano-trabalho/powerbi/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- permissão -----------------------------------------------------------

def test_anonymous_cannot_read_status():
    response = APIClient().get(STATUS_URL)

    assert response.status_code == 401


def test_anonymous_cannot_regenerate():
    response = APIClient().post(REGENERATE_URL)

    assert response.status_code == 401


@pytest.mark.parametrize("user_fixture", ["ugp_user", "adt_user"])
def test_non_super_admin_cannot_read_status(request, user_fixture):
    user = request.getfixturevalue(user_fixture)
    response = client_for(user).get(STATUS_URL)

    assert response.status_code == 403


@pytest.mark.parametrize("user_fixture", ["ugp_user", "adt_user"])
def test_non_super_admin_cannot_regenerate(request, user_fixture):
    user = request.getfixturevalue(user_fixture)
    response = client_for(user).post(REGENERATE_URL)

    assert response.status_code == 403


# --- GET status ------------------------------------------------------------

def test_status_before_any_token_generated(super_admin_user):
    response = client_for(super_admin_user).get(STATUS_URL)

    assert response.status_code == 200
    assert response.data == {
        "url_endpoint": "/api/v1/sgp/plano-trabalho/powerbi/",
        "token_mascarado": None,
        "atualizado_em": None,
        "status_snapshot": "sem_snapshot",
    }


def test_status_reflects_masked_token_after_regeneration(super_admin_user):
    client = client_for(super_admin_user)
    regenerated = client.post(REGENERATE_URL)

    response = client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.data["token_mascarado"] == regenerated.data["token_mascarado"]
    assert "token" not in response.data


def test_status_snapshot_em_dia_when_recent(super_admin_user):
    set_power_bi_snapshot({"atualizado_em": timezone.now().isoformat(), "resultados": []})

    response = client_for(super_admin_user).get(STATUS_URL)

    assert response.status_code == 200
    assert response.data["status_snapshot"] == "em_dia"


def test_status_snapshot_atrasado_after_one_hour(super_admin_user):
    antigo = timezone.now() - timedelta(hours=2)
    set_power_bi_snapshot({"atualizado_em": antigo.isoformat(), "resultados": []})

    response = client_for(super_admin_user).get(STATUS_URL)

    assert response.status_code == 200
    assert response.data["status_snapshot"] == "atrasado"
    assert response.data["atualizado_em"] == antigo.isoformat()


# --- regeneração -------------------------------------------------------------

def test_regenerate_returns_raw_token_only_once(super_admin_user):
    client = client_for(super_admin_user)

    response = client.post(REGENERATE_URL)

    assert response.status_code == 200
    assert response.data["token"]
    assert response.data["token_mascarado"].startswith("••••")
    assert response.data["token_mascarado"] != response.data["token"]

    status_response = client.get(STATUS_URL)
    assert "token" not in status_response.data
    assert response.data["token"] not in str(status_response.data)


def test_regenerate_persists_only_the_hash(super_admin_user):
    response = client_for(super_admin_user).post(REGENERATE_URL)

    token_raw = response.data["token"]
    stored = PowerBIToken.objects.get(ativo=True)
    assert stored.token_hash != token_raw
    assert token_raw not in stored.token_hash


def test_regenerate_does_not_leak_secret_in_audit_log(super_admin_user):
    response = client_for(super_admin_user).post(REGENERATE_URL)
    token_raw = response.data["token"]

    log = AuditLog.objects.filter(acao="power_bi_token.regenerated").latest("timestamp")

    assert token_raw not in str(log.valores_anteriores)
    assert token_raw not in str(log.valores_novos)
    assert log.valores_novos["token_mascarado"] == response.data["token_mascarado"]


def test_old_token_stops_authenticating_immediately_after_regeneration(super_admin_user):
    admin_client = client_for(super_admin_user)
    token_a = admin_client.post(REGENERATE_URL).data["token"]

    ok_with_a = APIClient().get(POWER_BI_URL, HTTP_AUTHORIZATION=f"Token {token_a}")
    assert ok_with_a.status_code == 200

    token_b = admin_client.post(REGENERATE_URL).data["token"]

    rejected_with_a = APIClient().get(POWER_BI_URL, HTTP_AUTHORIZATION=f"Token {token_a}")
    assert rejected_with_a.status_code == 401

    ok_with_b = APIClient().get(POWER_BI_URL, HTTP_AUTHORIZATION=f"Token {token_b}")
    assert ok_with_b.status_code == 200


# --- concorrência / integridade ---------------------------------------------

def test_database_rejects_a_second_active_token():
    """Rede de segurança da constraint uniq_power_bi_token_ativo.

    gerar() já desativa o token anterior antes de criar o novo, mas é a
    constraint que garante a invariante "no máximo um ativo" mesmo sob duas
    regenerações concorrentes — sem ela, a segunda `create()` de uma corrida
    entre requisições simultâneas deixaria dois tokens ativos ao mesmo tempo.
    """
    PowerBIToken.objects.create(token_hash="a" * 64, token_mascarado="••••aaaa")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PowerBIToken.objects.create(token_hash="b" * 64, token_mascarado="••••bbbb")


def test_gerar_retries_after_a_concurrent_active_token_conflict(super_admin_user):
    """Simula a corrida: a 1ª tentativa de `create()` esbarra na constraint
    (uma regeneração concorrente "venceu" nesse instante); gerar() recupera
    sozinho numa segunda tentativa, sem propagar erro pro chamador.
    """
    original_create = PowerBIToken.objects.create
    chamadas = []

    def create_falha_na_primeira_vez(**kwargs):
        chamadas.append(kwargs)
        if len(chamadas) == 1:
            raise IntegrityError("condição de corrida simulada")
        return original_create(**kwargs)

    with patch.object(PowerBIToken.objects, "create", side_effect=create_falha_na_primeira_vez):
        instancia, token_raw = PowerBIToken.gerar(criado_por=super_admin_user)

    assert len(chamadas) == 2
    assert PowerBIToken.objects.filter(ativo=True).count() == 1
    assert PowerBIToken.objects.get(ativo=True).pk == instancia.pk
    assert PowerBIToken.validar(token_raw)


# --- compatibilidade com a env var (canal secundário) -------------------------

def test_legacy_env_var_still_authenticates_when_no_persisted_token(settings):
    settings.POWER_BI_SERVICE_TOKEN = "legacy-token"

    response = APIClient().get(POWER_BI_URL, HTTP_AUTHORIZATION="Token legacy-token")

    assert response.status_code == 200


def test_persisted_token_authenticates_without_env_var(settings, super_admin_user):
    settings.POWER_BI_SERVICE_TOKEN = ""
    token_raw = client_for(super_admin_user).post(REGENERATE_URL).data["token"]

    response = APIClient().get(POWER_BI_URL, HTTP_AUTHORIZATION=f"Token {token_raw}")

    assert response.status_code == 200
