import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    MunicipalityFactory,
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgp.tests.factories import ProjetoFactory


# ──────────────────────────────────────────────────────────────
# Cache — limpa antes e depois de cada teste (throttles, etc.)
# ──────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def limpa_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def state_rn(db):
    return StateFactory(sigla="RN", nome="Rio Grande do Norte")


@pytest.fixture
def state_ce(db):
    return StateFactory(sigla="CE", nome="Ceará")


@pytest.fixture
def territory(db):
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def outro_territory(db):
    return TerritoryFactory(nome="Território CE", estados=["CE"])


@pytest.fixture
def municipio(db, state_rn, territory):
    return MunicipalityFactory(
        nome="Mossoró",
        state=state_rn,
        territory=territory,
        codigo_ibge="2408003",
    )


@pytest.fixture
def municipio_outro(db, state_ce, outro_territory):
    return MunicipalityFactory(
        nome="Fortaleza",
        state=state_ce,
        territory=outro_territory,
        codigo_ibge="2304400",
    )


@pytest.fixture
def projeto(db):
    return ProjetoFactory(nome="Projeto Teste")


@pytest.fixture
def role_adt(db):
    return RoleFactory(slug="adt-acr", nome="ADT / ACR")


@pytest.fixture
def articulador(db, territory):
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    user = UserFactory(email="articulador@test.com", nome="Articulador RN", profiles=[(role, territory)])
    territory.articulador = user
    territory.save(update_fields=["articulador"])
    return user


@pytest.fixture
def usuario(db, role_adt, territory):
    return UserFactory(email="adt@test.com", nome="ADT RN", profiles=[(role_adt, territory)])


@pytest.fixture
def auth_client(api_client, usuario):
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.fixture
def super_admin_user(db):
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    return UserFactory(email="super@admin.com", nome="Super Admin", profiles=[(role, None)])


@pytest.fixture
def auth_client_super_admin(api_client, super_admin_user):
    api_client.force_authenticate(user=super_admin_user)
    return api_client


# ──────────────────────────────────────────────────────────────
# Helpers de payload
# ──────────────────────────────────────────────────────────────

def payload_upf(projeto, municipio, **overrides):
    payload = {
        "projeto": projeto.pk,
        "municipio": municipio.pk,
        "territorio": municipio.territory.pk,
        "titular": {
            "nome_completo": "Maria da Silva",
            "cpf": "86288366757",
        },
        "apelido": "Maria",
        "whatsapp": "",
        "latitude": "-5.123456",
        "longitude": "-37.654321",
    }
    payload.update(overrides)
    return payload
