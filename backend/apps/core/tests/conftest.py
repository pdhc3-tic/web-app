import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from apps.core.tests.factories import UserFactory, RoleFactory, TerritoryFactory
from apps.core.models.user_profile import UserProfile


# ──────────────────────────────────────────────────────────────
# Cache — limpa antes e depois de cada teste para evitar
# contaminação entre testes (LocMemCache persiste no processo).
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
def user_factory():
    return UserFactory


@pytest.fixture
def role_factory():
    return RoleFactory


@pytest.fixture
def territory_factory():
    return TerritoryFactory


@pytest.fixture
def super_admin_user(db):
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    user = UserFactory(email="super@admin.com", nome="Super Admin", is_superuser=True)
    UserProfile.objects.create(user=user, perfil=role)
    return user


@pytest.fixture
def ugp_user(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    user = UserFactory(email="ugp@test.com", nome="UGP User")
    UserProfile.objects.create(user=user, perfil=role)
    return user


@pytest.fixture
def adt_user(db):
    role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
    user = UserFactory(email="adt@test.com", nome="ADT User")
    UserProfile.objects.create(user=user, perfil=role)
    return user
