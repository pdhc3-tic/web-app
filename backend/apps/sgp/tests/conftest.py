import pytest
from rest_framework.test import APIClient

from apps.core.models import Municipality, State, Role
from apps.core.tests.factories import UserFactory, RoleFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def state_rn(db):
    return State.objects.get_or_create(
        sigla='RN', defaults={'nome': 'Rio Grande do Norte'}
    )[0]


@pytest.fixture
def municipio(state_rn):
    return Municipality.objects.create(
        nome='Mossoró',
        state=state_rn,
        codigo_ibge='2408003',
    )


@pytest.fixture
def outro_municipio(state_rn):
    return Municipality.objects.create(
        nome='Upanema',
        state=state_rn,
        codigo_ibge='2414500',
    )


@pytest.fixture
def role_super_admin(db):
    return Role.objects.get_or_create(
        slug='super-admin', defaults={'nome': 'Super Admin'}
    )[0]


@pytest.fixture
def role_ugp(db):
    return Role.objects.get_or_create(
        slug='ugp', defaults={'nome': 'UGP'}
    )[0]


@pytest.fixture
def role_adt(db):
    return Role.objects.get_or_create(
        slug='adt-acr', defaults={'nome': 'ADT / ACR'}
    )[0]


@pytest.fixture
def super_admin_client(role_super_admin):
    user = UserFactory(role=role_super_admin)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def ugp_client(role_ugp):
    user = UserFactory(role=role_ugp)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def adt_client(role_adt):
    user = UserFactory(role=role_adt)
    client = APIClient()
    client.force_authenticate(user=user)
    return client
