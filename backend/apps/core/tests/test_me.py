import pytest
from rest_framework.test import APIClient
from apps.core.tests.factories import UserFactory, RoleFactory, TerritoryFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    return UserFactory()

@pytest.mark.django_db
def test_me_retorna_200(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 200

@pytest.mark.django_db
def test_me_campos_presentes(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    campos = ["id", "nome_completo", "email", "telefone", "whatsapp", "foto_url", "ultimo_login", "perfis", "territorios", "permissoes_resumo"]
    for campo in campos:
        assert campo in response.data

@pytest.mark.django_db
def test_me_perfis_vazio_sem_role(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert response.data["perfis"] == []

@pytest.mark.django_db
def test_me_perfis_com_role(client):
    role = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    usuario = UserFactory(role=role)
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert len(response.data["perfis"]) == 1
    assert response.data["perfis"][0]["slug"] == "adt-acr"
    assert response.data["perfis"][0]["nome"] == "ADT/ACR"

@pytest.mark.django_db
def test_me_territorios_vazio_sem_vinculo(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert response.data["territorios"] == []

@pytest.mark.django_db
def test_me_territorios_com_vinculo(client):
    territorio = TerritoryFactory(nome="Sertão do Apodi", estados=["RN"])
    usuario = UserFactory()
    usuario.territorios.add(territorio)
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert len(response.data["territorios"]) == 1
    assert response.data["territorios"][0]["nome"] == "Sertão do Apodi"
    assert response.data["territorios"][0]["estados"] == ["RN"]

@pytest.mark.django_db
def test_me_campos_telefone_whatsapp_foto(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert "telefone" in response.data
    assert "whatsapp" in response.data
    assert "foto_url" in response.data

@pytest.mark.django_db
def test_me_permissoes_resumo_presente(client, usuario):
    client.force_authenticate(user=usuario)
    response = client.get("/api/v1/auth/me/")
    assert "permissoes_resumo" in response.data
    assert isinstance(response.data["permissoes_resumo"], list)