"""
Matriz de isolamento territorial dos endpoints de listagem do SGP que usam
`apps.sgp.services.access.scope_queryset` — a rede de segurança que garante
que UPF, Atividade e Técnico nunca vazam dado entre territórios/estados.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.tests.factories import ActivityFactory, TecnicoFactory, UPFFactory

pytestmark = pytest.mark.django_db

LIST_URLS = {
    "upfs": "/api/v1/upfs/",
    "atividades": "/api/v1/sgp/atividades/",
    "tecnicos": "/api/v1/sgp/tecnicos/",
}


def _ids(response):
    return {item["id"] for item in response.data["results"]}


@pytest.fixture
def entidade_rn(municipio_rn, territory_rn, projeto):
    return {
        "upfs": UPFFactory(municipio=municipio_rn, projeto=projeto, territorio=territory_rn),
        "atividades": ActivityFactory(municipio=municipio_rn),
        "tecnicos": TecnicoFactory(territorio=territory_rn),
    }


@pytest.fixture
def entidade_ce(municipio_ce, territory_ce, projeto):
    return {
        "upfs": UPFFactory(municipio=municipio_ce, projeto=projeto, territorio=territory_ce),
        "atividades": ActivityFactory(municipio=municipio_ce),
        "tecnicos": TecnicoFactory(territorio=territory_ce),
    }


# ===========================================================================
# 1 — matriz endpoint × perfil: o conjunto de IDs é exatamente o esperado
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_matriz_endpoints_x_perfis(
    endpoint, entidade_rn, entidade_ce,
    usuario_super_admin, usuario_articulador_rn, usuario_adt_rn,
):
    # Cliente próprio por perfil — os fixtures auth_client_* de conftest.py
    # compartilham a mesma instância de api_client (força autenticação nela),
    # o que quebra ao pedir mais de um no mesmo teste: o último force_authenticate
    # vence pros três. Aqui cada perfil autentica numa instância nova.
    url = LIST_URLS[endpoint]
    id_rn = entidade_rn[endpoint].pk
    id_ce = entidade_ce[endpoint].pk

    client_super = APIClient()
    client_super.force_authenticate(user=usuario_super_admin)
    resp_super = client_super.get(url)
    assert resp_super.status_code == status.HTTP_200_OK
    assert {id_rn, id_ce} <= _ids(resp_super)

    client_art = APIClient()
    client_art.force_authenticate(user=usuario_articulador_rn)
    resp_art = client_art.get(url)
    assert resp_art.status_code == status.HTTP_200_OK
    assert _ids(resp_art) == {id_rn}

    client_adt = APIClient()
    client_adt.force_authenticate(user=usuario_adt_rn)
    resp_adt = client_adt.get(url)
    assert resp_adt.status_code == status.HTTP_200_OK
    assert _ids(resp_adt) == {id_rn}


# ===========================================================================
# 2 — adt-acr nunca vê outro território
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_adt_nunca_ve_outro_territorio(endpoint, entidade_rn, entidade_ce, auth_client_adt_rn):
    response = auth_client_adt_rn.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert entidade_ce[endpoint].pk not in _ids(response)


# ===========================================================================
# 3 — articulador-estadual nunca vê outro estado
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_articulador_nunca_ve_outro_estado(endpoint, entidade_rn, entidade_ce, auth_client_articulador_rn):
    response = auth_client_articulador_rn.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert entidade_ce[endpoint].pk not in _ids(response)


# ===========================================================================
# 4 — ugp vê tudo
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_ugp_ve_tudo(endpoint, entidade_rn, entidade_ce, ugp_client):
    response = ugp_client.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert {entidade_rn[endpoint].pk, entidade_ce[endpoint].pk} <= _ids(response)


# ===========================================================================
# 5 — usuário sem nenhum perfil com escopo é bloqueado (403) em todos
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_sem_perfil_bloqueado(endpoint, entidade_rn, auth_client_sem_acesso):
    response = auth_client_sem_acesso.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 6 — adt-acr sem território atribuído recebe conjunto vazio, nunca o total
# ===========================================================================

@pytest.mark.parametrize("endpoint", ["upfs", "atividades", "tecnicos"])
def test_usuario_sem_territorio_nao_vaza(endpoint, entidade_rn, entidade_ce, api_client):
    role_adt = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    user = UserFactory(profiles=[(role_adt, None)])
    api_client.force_authenticate(user=user)

    response = api_client.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK, response.data
    assert _ids(response) == set()
