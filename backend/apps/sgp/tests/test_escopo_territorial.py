"""
Matriz de isolamento territorial dos endpoints de listagem do SGP que usam
`apps.sgp.services.access.scope_queryset`/`resolver_escopo` — a rede de
segurança que garante que UPF, Atividade, Técnico, Ação e Meta do Plano de
Trabalho nunca vazam dado entre territórios/estados.

Os recursos aninhados sob uma UPF específica (documentos, produção,
membros, formulários) não têm forma de lista territorialmente filtrada —
dependem de resolver a UPF-pai dentro do escopo do usuário via
`get_object_or_404`, então o isolamento deles é testado à parte, pelo
comportamento esperado (404 pra UPF fora do escopo), não pela matriz de IDs.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.tests.factories import (
    ActivityFactory,
    TecnicoFactory,
    UPFFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

LIST_URLS = {
    "upfs": "/api/v1/upfs/",
    "atividades": "/api/v1/sgp/atividades/",
    "tecnicos": "/api/v1/sgp/tecnicos/",
    "acoes": "/api/v1/acoes/",
    "metas": "/api/v1/metas/",
}

NESTED_UPF_URLS = {
    "upf_documentos": "/api/v1/upfs/{upf_pk}/documentos/",
    "upf_producao": "/api/v1/upfs/{upf_pk}/producao/",
    "upf_membros": "/api/v1/sgp/upfs/{upf_pk}/membros/",
    "upf_formularios": "/api/v1/sgp/upfs/{upf_pk}/formularios/",
}


def _ids(response):
    return {item["id"] for item in response.data["results"]}


def _entidade(municipio, territorio, projeto, *, numero_meta):
    """Cria uma UPF, uma Atividade (com sua Ação/Meta) e um Técnico, todos no
    mesmo município/território — usados pra montar os dois lados (RN/CE) da
    matriz. A Atividade tem `acao` explícita pra a Ação/Meta ficarem no
    mesmo escopo territorial dela (Ação/Meta não têm território próprio,
    herdam de suas Atividades — ver `services/workplan_access.py`)."""
    meta = WorkPlanMetaFactory(numero=numero_meta)
    acao = WorkPlanAcaoFactory(meta=meta, numero=f"{numero_meta}.1")
    atividade = ActivityFactory(acao=acao, municipio=municipio)
    return {
        "upfs": UPFFactory(municipio=municipio, projeto=projeto, territorio=territorio),
        "atividades": atividade,
        "tecnicos": TecnicoFactory(territorio=territorio),
        "acoes": acao,
        "metas": meta,
    }


@pytest.fixture
def entidade_rn(municipio_rn, territory_rn, projeto):
    return _entidade(municipio_rn, territory_rn, projeto, numero_meta=1)


@pytest.fixture
def entidade_ce(municipio_ce, territory_ce, projeto):
    return _entidade(municipio_ce, territory_ce, projeto, numero_meta=2)


ENDPOINTS = ["upfs", "atividades", "tecnicos", "acoes", "metas"]


# ===========================================================================
# 1 — matriz endpoint × perfil: o conjunto de IDs é exatamente o esperado
# ===========================================================================

@pytest.mark.parametrize("endpoint", ENDPOINTS)
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
    assert _ids(resp_super) == {id_rn, id_ce}

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

@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_adt_nunca_ve_outro_territorio(endpoint, entidade_rn, entidade_ce, auth_client_adt_rn):
    response = auth_client_adt_rn.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert entidade_ce[endpoint].pk not in _ids(response)


# ===========================================================================
# 3 — articulador-estadual nunca vê outro estado
# ===========================================================================

@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_articulador_nunca_ve_outro_estado(endpoint, entidade_rn, entidade_ce, auth_client_articulador_rn):
    response = auth_client_articulador_rn.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert entidade_ce[endpoint].pk not in _ids(response)


# ===========================================================================
# 4 — ugp vê tudo
# ===========================================================================

@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_ugp_ve_tudo(endpoint, entidade_rn, entidade_ce, ugp_client):
    response = ugp_client.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == {entidade_rn[endpoint].pk, entidade_ce[endpoint].pk}


# ===========================================================================
# 5 — usuário sem nenhum perfil com escopo é bloqueado (403) em todos —
# inclui fgd, que tem acesso a demandas mas não a nada territorial do SGP.
# ===========================================================================

@pytest.mark.parametrize("client_fixture", ["auth_client_sem_acesso", "auth_client_fgd"])
@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_sem_perfil_bloqueado(endpoint, client_fixture, entidade_rn, request):
    client = request.getfixturevalue(client_fixture)
    response = client.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# 6 — adt-acr sem território atribuído recebe conjunto vazio, nunca o total
# ===========================================================================

@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_usuario_sem_territorio_nao_vaza(endpoint, entidade_rn, entidade_ce, api_client):
    role_adt = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    user = UserFactory(profiles=[(role_adt, None)])
    api_client.force_authenticate(user=user)

    response = api_client.get(LIST_URLS[endpoint])
    assert response.status_code == status.HTTP_200_OK, response.data
    assert _ids(response) == set()


# ===========================================================================
# 7 — recursos aninhados sob UPF (documentos, produção, membros,
# formulários): sem lista territorial própria, dependem de resolver a
# UPF-pai no escopo do usuário — fora do escopo dá 404, não lista vazia.
# ===========================================================================

@pytest.mark.parametrize("recurso", list(NESTED_UPF_URLS))
def test_recursos_aninhados_sob_upf_fora_do_territorio_dao_404(
    recurso, entidade_rn, entidade_ce, auth_client_adt_rn,
):
    url_fora = NESTED_UPF_URLS[recurso].format(upf_pk=entidade_ce["upfs"].pk)
    response_fora = auth_client_adt_rn.get(url_fora)
    assert response_fora.status_code == status.HTTP_404_NOT_FOUND

    url_dentro = NESTED_UPF_URLS[recurso].format(upf_pk=entidade_rn["upfs"].pk)
    response_dentro = auth_client_adt_rn.get(url_dentro)
    assert response_dentro.status_code == status.HTTP_200_OK
