"""Cenários que o `seed_demo` garante para as specs do Playwright.

O ADT com que os E2E fazem login precisa enxergar, no próprio escopo, uma UPF
com a cascata Estado → Município → Território → Comunidade, uma atividade
concluída sem evidência, uma atividade atrasada e uma Ação vermelha no painel —
e a mesma Ação precisa estar vermelha na visão global.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import UserProfile
from apps.sgp.management.commands.seed_demo import TECNICOS, email_de_demo
from apps.sgp.models import UPF, Activity
from apps.sgp.models.activity import filtro_atrasada
from apps.sgp.services.workplan_dashboard import (
    dashboard_actions,
    dashboard_actions_for_user,
    enrich_dashboard_action,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def adt_do_e2e():
    call_command("seed_core")
    call_command("seed_demo", "--no-files", "--upfs", "8", "--atividades", "6")
    primeiro, ultimo, _ = TECNICOS[0]
    return User.objects.get(email=email_de_demo(primeiro, ultimo))


@pytest.fixture
def territorio(adt_do_e2e):
    return UserProfile.objects.get(
        user=adt_do_e2e, perfil__slug="adt-acr", territorio__isnull=False
    ).territorio


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


def _vermelhas(acoes):
    hoje = timezone.localdate()
    return {
        a.pk for a in acoes
        if enrich_dashboard_action(a, today=hoje).dashboard_semaforo == "vermelho"
    }


def test_upf_com_cascata_completa_no_territorio_do_adt(adt_do_e2e, territorio):
    upf = UPF.objects.filter(
        territorio=territorio, ativo=True, comunidade__isnull=False
    ).select_related("municipio__state", "comunidade").first()

    assert upf is not None
    assert upf.municipio.state_id is not None
    assert upf.municipio.territory_id == territorio.pk
    assert upf.comunidade.municipio_id == upf.municipio_id

    response = _cliente(adt_do_e2e).get("/api/v1/upfs/", {"territorio": territorio.pk})
    assert upf.pk in {item["id"] for item in response.data["results"]}


def test_atividade_sem_evidencia_no_escopo_do_adt(adt_do_e2e, territorio):
    assert Activity.objects.filter(
        municipio__territory=territorio, status="concluido_sem_evidencia"
    ).exists()

    response = _cliente(adt_do_e2e).get(
        "/api/v1/sgp/atividades/", {"status": "concluido_sem_evidencia"}
    )
    assert response.data["count"] >= 1


def test_atividade_atrasada_no_escopo_do_adt(adt_do_e2e, territorio):
    assert Activity.objects.filter(
        filtro_atrasada(timezone.now()), municipio__territory=territorio
    ).exists()

    response = _cliente(adt_do_e2e).get("/api/v1/sgp/atividades/", {"atrasada": "true"})
    assert response.data["count"] >= 1


def test_acao_vermelha_para_o_adt_e_na_visao_global(adt_do_e2e):
    assert _vermelhas(dashboard_actions_for_user(adt_do_e2e)) & _vermelhas(dashboard_actions())
