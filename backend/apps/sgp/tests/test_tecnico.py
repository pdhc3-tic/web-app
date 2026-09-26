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


# ===========================================================================
# Pendências da Sprint 9d — nomes, paginação, elegíveis e erros com `code`
# ===========================================================================

ELEGIVEIS_URL = "/api/v1/sgp/tecnicos/usuarios-elegiveis/"


@pytest.mark.django_db
def test_listagem_expoe_nomes(auth_client_super_admin, territory_rn):
    osc = OrganizationFactory(nome="OSC Sertão")
    tecnico = TecnicoFactory(
        user=UserFactory(nome="Joana Lima"), territorio=territory_rn, osc=osc
    )

    response = auth_client_super_admin.get(LIST_URL)

    item = next(i for i in response.data["results"] if i["id"] == tecnico.pk)
    assert item["user_nome"] == "Joana Lima"
    assert item["territorio_nome"] == territory_rn.nome
    assert item["osc_nome"] == "OSC Sertão"


@pytest.mark.django_db
def test_nomes_nulos_quando_sem_territorio_e_sem_osc(auth_client_super_admin):
    tecnico = TecnicoFactory(territorio=None, osc=None)

    response = auth_client_super_admin.get(detail_url(tecnico.pk))

    assert response.data["territorio_nome"] is None
    assert response.data["osc_nome"] is None


@pytest.mark.django_db
def test_paginacao_limit_offset(auth_client_super_admin):
    TecnicoFactory.create_batch(5)

    primeira = auth_client_super_admin.get(LIST_URL, {"limit": 2, "offset": 0}).data
    segunda = auth_client_super_admin.get(LIST_URL, {"limit": 2, "offset": 2}).data

    assert primeira["count"] == 5
    assert len(primeira["results"]) == 2
    ids_primeira = {i["id"] for i in primeira["results"]}
    ids_segunda = {i["id"] for i in segunda["results"]}
    assert ids_primeira.isdisjoint(ids_segunda)


@pytest.mark.django_db
def test_usuarios_elegiveis_exclui_quem_ja_e_tecnico(ugp_client):
    livre = UserFactory(nome="Ana Livre")
    TecnicoFactory(user=UserFactory(nome="Ana Técnica"))
    inativo = TecnicoFactory(user=UserFactory(nome="Ana Técnica Inativa"), ativo=False)
    UserFactory(nome="Ana Desligada", ativo=False)

    response = ugp_client.get(ELEGIVEIS_URL, {"q": "ana", "limit": 50})

    assert response.status_code == status.HTTP_200_OK
    nomes = [u["nome_completo"] for u in response.data["results"]]
    assert nomes == ["Ana Livre"]
    assert response.data["results"][0]["id"] == livre.pk
    assert inativo.user.nome not in nomes


@pytest.mark.django_db
def test_usuarios_elegiveis_restrito_a_ugp_e_super_admin(auth_client_adt_rn, auth_client_super_admin):
    assert auth_client_adt_rn.get(ELEGIVEIS_URL).status_code == status.HTTP_403_FORBIDDEN
    assert auth_client_super_admin.get(ELEGIVEIS_URL).status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_erro_tecnico_duplicado(auth_client_super_admin):
    existente = TecnicoFactory()

    response = auth_client_super_admin.post(
        LIST_URL, data={"user": existente.user_id, "papel": "adt-acr"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "tecnico_duplicado"
    assert response.data["message"]


@pytest.mark.django_db
def test_editar_o_proprio_tecnico_nao_e_duplicado(auth_client_super_admin):
    tecnico = TecnicoFactory()

    response = auth_client_super_admin.put(
        detail_url(tecnico.pk),
        data={"user": tecnico.user_id, "papel": "novo papel", "ativo": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK, response.data


@pytest.mark.django_db
def test_erro_conflito_vinculo_osc_fora_do_territorio(auth_client_super_admin, territory_rn, territory_ce):
    osc = OrganizationFactory()
    osc.territorios.add(territory_ce)

    response = auth_client_super_admin.post(
        LIST_URL,
        data={
            "user": UserFactory().pk,
            "territorio": territory_rn.pk,
            "osc": osc.pk,
            "papel": "adt-acr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "conflito_vinculo"


@pytest.mark.django_db
def test_conflito_vinculo_tambem_no_patch(auth_client_super_admin, territory_rn, territory_ce):
    osc = OrganizationFactory()
    osc.territorios.add(territory_ce)
    tecnico = TecnicoFactory(territorio=territory_rn, osc=None)

    response = auth_client_super_admin.patch(
        detail_url(tecnico.pk), data={"osc": osc.pk}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "conflito_vinculo"


@pytest.mark.django_db
def test_osc_sem_territorio_cadastrado_nao_gera_conflito(auth_client_super_admin, territory_rn):
    response = auth_client_super_admin.post(
        LIST_URL,
        data={
            "user": UserFactory().pk,
            "territorio": territory_rn.pk,
            "osc": OrganizationFactory().pk,
            "papel": "adt-acr",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED, response.data


@pytest.mark.django_db
def test_erro_tecnico_ja_inativo(auth_client_super_admin):
    tecnico = TecnicoFactory(ativo=False)

    response = auth_client_super_admin.delete(detail_url(tecnico.pk))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["code"] == "tecnico_ja_inativo"
