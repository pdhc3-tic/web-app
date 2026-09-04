"""
Testes para o model/endpoint Tecnico (Issue #225).

Cobertura (tabela da issue):
    1. test_crud_tecnico — criar, listar, editar, desativar
    2. test_apenas_ugp_escreve — ADT recebe 403 no POST
    3. test_escopo_territorial_na_leitura — ADT vê só técnicos do seu território
    4. test_migration_cria_tecnicos — usuários adt-acr existentes ganham Tecnico
       com o território correto
    5. test_filtro_por_osc — retorna só os vinculados à OSC
    6. test_atividade_filtra_por_osc_do_tecnico — ActivityFilter funcional
    7. test_desativar_preserva_atividades — atividades históricas intactas
"""
import importlib

import pytest
from django.apps import apps as django_apps
from rest_framework import status

from apps.core.tests.factories import (
    OrganizationFactory,
    RoleFactory,
    UserFactory,
)
from apps.sgp.models import Tecnico
from apps.sgp.tests.factories import ActivityFactory, TecnicoFactory

LIST_URL = "/api/v1/sgp/tecnicos/"
ATIVIDADES_URL = "/api/v1/sgp/atividades/"


def detail_url(pk):
    return f"/api/v1/sgp/tecnicos/{pk}/"


# ===========================================================================
# Teste 1 — CRUD completo (criar, listar, editar, desativar)
# ===========================================================================

@pytest.mark.django_db
def test_crud_tecnico(auth_client_super_admin, territory_rn):
    osc = OrganizationFactory()
    user = UserFactory()
    payload = {
        "user": user.pk,
        "territorio": territory_rn.pk,
        "osc": osc.pk,
        "papel": "adt-acr",
        "ativo": True,
    }

    response = auth_client_super_admin.post(LIST_URL, data=payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED, response.data
    tecnico_id = response.data["id"]

    response = auth_client_super_admin.get(LIST_URL)
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert tecnico_id in ids

    response = auth_client_super_admin.patch(
        detail_url(tecnico_id), data={"papel": "articulador-estadual"}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    assert response.data["papel"] == "articulador-estadual"

    response = auth_client_super_admin.delete(detail_url(tecnico_id))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Tecnico.objects.get(pk=tecnico_id).ativo is False


# ===========================================================================
# Teste 2 — escrita restrita a UGP/Super Admin
# ===========================================================================

@pytest.mark.django_db
def test_apenas_ugp_escreve(auth_client_adt_rn, territory_rn):
    osc = OrganizationFactory()
    user = UserFactory()
    payload = {
        "user": user.pk,
        "territorio": territory_rn.pk,
        "osc": osc.pk,
        "papel": "adt-acr",
    }

    response = auth_client_adt_rn.post(LIST_URL, data=payload, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# Teste 3 — escopo territorial na leitura
# ===========================================================================

@pytest.mark.django_db
def test_escopo_territorial_na_leitura(auth_client_adt_rn, territory_rn, territory_ce):
    tecnico_rn = TecnicoFactory(territorio=territory_rn)
    tecnico_ce = TecnicoFactory(territorio=territory_ce)

    response = auth_client_adt_rn.get(LIST_URL)
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert tecnico_rn.pk in ids
    assert tecnico_ce.pk not in ids


# ===========================================================================
# Teste 4 — migração de dados cria Tecnico para perfis existentes
# ===========================================================================

@pytest.mark.django_db
def test_migration_cria_tecnicos(territory_rn):
    role = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    user = UserFactory(profiles=[(role, territory_rn)])

    migration_module = importlib.import_module(
        "apps.sgp.migrations.0019_cria_tecnicos_perfis_existentes"
    )
    migration_module.cria_tecnicos_para_perfis_existentes(django_apps, None)

    tecnico = Tecnico.objects.get(user=user)
    assert tecnico.territorio_id == territory_rn.pk
    assert tecnico.papel == "adt-acr"
    assert tecnico.ativo is True


# ===========================================================================
# Teste 5 — filtro ?osc= na listagem de técnicos
# ===========================================================================

@pytest.mark.django_db
def test_filtro_por_osc(auth_client_super_admin):
    osc_a = OrganizationFactory()
    osc_b = OrganizationFactory()
    tecnico_a = TecnicoFactory(osc=osc_a)
    TecnicoFactory(osc=osc_b)

    response = auth_client_super_admin.get(LIST_URL, {"osc": osc_a.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [tecnico_a.pk]


# ===========================================================================
# Teste 6 — ActivityFilter por OSC do técnico responsável
# ===========================================================================

@pytest.mark.django_db
def test_atividade_filtra_por_osc_do_tecnico(auth_client_super_admin):
    osc_a = OrganizationFactory()
    osc_b = OrganizationFactory()
    tecnico_a = TecnicoFactory(osc=osc_a)
    tecnico_b = TecnicoFactory(osc=osc_b)

    atividade_a = ActivityFactory(tecnico_responsavel=tecnico_a.user)
    ActivityFactory(tecnico_responsavel=tecnico_b.user)

    response = auth_client_super_admin.get(ATIVIDADES_URL, {"osc": osc_a.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [atividade_a.pk]


# ===========================================================================
# Teste 7 — desativar Tecnico preserva atividades históricas
# ===========================================================================

@pytest.mark.django_db
def test_desativar_preserva_atividades(auth_client_super_admin):
    tecnico = TecnicoFactory()
    atividade = ActivityFactory(tecnico_responsavel=tecnico.user)

    response = auth_client_super_admin.delete(detail_url(tecnico.pk))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    atividade.refresh_from_db()
    assert atividade.tecnico_responsavel_id == tecnico.user_id
    assert atividade.ativo is True
