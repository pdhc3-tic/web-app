import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.sgp.models import Cultura, EspecieAnimal

pytestmark = pytest.mark.django_db

CULTURAS_URL = "/api/v1/catalogos/culturas/"
ESPECIES_URL = "/api/v1/catalogos/especies-animais/"


@pytest.fixture
def catalogos_seed(db):
    call_command("seed_sgp", verbosity=0)


def test_seeds_insert_minimum_culturas():
    call_command("seed_sgp", verbosity=0)

    assert Cultura.objects.count() >= 50


def test_seeds_insert_minimum_especies():
    call_command("seed_sgp", verbosity=0)

    assert EspecieAnimal.objects.count() >= 20


def test_list_culturas_paginated(auth_client, catalogos_seed):
    response = auth_client.get(CULTURAS_URL)

    assert response.status_code == 200
    assert response.data["count"] >= 50
    assert len(response.data["results"]) == 50


def test_list_culturas_search_by_nome(auth_client, catalogos_seed):
    response = auth_client.get(f"{CULTURAS_URL}?q=feijão")

    assert response.status_code == 200
    nomes = [item["nome"].lower() for item in response.data["results"]]
    assert nomes
    assert all("feijão" in nome for nome in nomes)


def test_list_culturas_filter_by_categoria(auth_client, catalogos_seed):
    response = auth_client.get(f"{CULTURAS_URL}?categoria=graos")

    assert response.status_code == 200
    assert response.data["results"]
    assert all(item["categoria"] == "graos" for item in response.data["results"])


def test_list_especies_animais_filter_by_categoria(auth_client, catalogos_seed):
    response = auth_client.get(f"{ESPECIES_URL}?categoria=caprino")

    assert response.status_code == 200
    assert response.data["results"]
    assert all(item["categoria"] == "caprino" for item in response.data["results"])


def test_list_default_only_active(auth_client, catalogos_seed):
    Cultura.objects.create(
        nome="Cultura Inativa Teste",
        categoria="graos",
        ciclo="anual",
        ativa=False,
    )

    response = auth_client.get(CULTURAS_URL)

    assert response.status_code == 200
    nomes = [item["nome"] for item in response.data["results"]]
    assert "Cultura Inativa Teste" not in nomes


def test_list_ativa_false_shows_all_only_for_admin(
    usuario_sem_acesso, usuario_super_admin, catalogos_seed
):
    Cultura.objects.create(
        nome="Cultura Ativa Teste",
        categoria="graos",
        ciclo="anual",
        ativa=True,
    )
    Cultura.objects.create(
        nome="Cultura Inativa Teste",
        categoria="graos",
        ciclo="anual",
        ativa=False,
    )

    user_client = APIClient()
    user_client.force_authenticate(user=usuario_sem_acesso)
    admin_client = APIClient()
    admin_client.force_authenticate(user=usuario_super_admin)

    user_response = user_client.get(f"{CULTURAS_URL}?ativa=false&page_size=200")
    admin_response = admin_client.get(
        f"{CULTURAS_URL}?ativa=false&page_size=200"
    )

    assert user_response.status_code == 200
    user_nomes = [item["nome"] for item in user_response.data["results"]]
    assert "Cultura Ativa Teste" in user_nomes
    assert "Cultura Inativa Teste" not in user_nomes

    assert admin_response.status_code == 200
    admin_nomes = [item["nome"] for item in admin_response.data["results"]]
    assert "Cultura Ativa Teste" in admin_nomes
    assert "Cultura Inativa Teste" in admin_nomes


def test_list_requires_authentication(api_client):
    response = api_client.get(CULTURAS_URL)

    assert response.status_code == 401


def test_no_post_endpoint_exposed(auth_client):
    response = auth_client.post(
        CULTURAS_URL,
        {"nome": "Nova Cultura", "categoria": "graos", "ciclo": "anual"},
        format="json",
    )

    assert response.status_code == 405
