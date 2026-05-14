import pytest

from apps.core.models.role import Role
from apps.core.models.territory import Territory
from apps.core.permissions import _resolve_territorio_id
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.core.tests.factories import TerritoryFactory, UserFactory, UserProfileFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def role_super():
    return Role.objects.get_or_create(slug="super-admin", defaults={"nome": "Super Admin"})[0]


@pytest.fixture
def role_ugp():
    return Role.objects.get_or_create(slug="ugp", defaults={"nome": "UGP"})[0]


@pytest.fixture
def role_adt():
    return Role.objects.get_or_create(slug="adt-acr", defaults={"nome": "ADT / ACR"})[0]


@pytest.fixture
def territory_rn():
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def territory_pb():
    return TerritoryFactory(nome="Território PB", estados=["PB"])


@pytest.fixture
def territory_ce():
    return TerritoryFactory(nome="Território CE", estados=["CE"])


class TestUserHasRole:
    def test_matching(self, role_super):
        assert user_has_role(UserFactory(role=role_super), "super-admin") is True

    def test_mismatch(self, role_ugp):
        assert user_has_role(UserFactory(role=role_ugp), "super-admin") is False

    def test_no_role(self):
        assert user_has_role(UserFactory(role=None), "super-admin") is False


class TestUserTerritories:
    def test_with_territories(self, territory_rn, territory_pb):
        user = UserFactory()
        user.territorios.add(territory_rn, territory_pb)
        assert set(user_territories(user).values_list("pk", flat=True)) == {
            territory_rn.pk,
            territory_pb.pk,
        }

    def test_global_without_territories(self, territory_rn):
        user = UserFactory()
        assert user_territories(user).count() == Territory.objects.count()


class TestUserStates:
    def test_with_territories(self, territory_rn, territory_pb):
        user = UserFactory()
        user.territorios.add(territory_rn, territory_pb)
        assert user_states(user) == {"RN", "PB"}

    def test_global_without_territories(self, territory_rn, territory_ce):
        user = UserFactory()
        states = user_states(user)
        assert "RN" in states and "CE" in states


class TestResolveTerritorioId:
    def test_direct(self):
        class Obj:
            territorio_id = 42
        assert _resolve_territorio_id(Obj(), "territorio_id") == 42

    def test_nested(self):
        class Upf:
            territorio_id = 99
        class Obj:
            upf = Upf()
        assert _resolve_territorio_id(Obj(), "upf.territorio_id") == 99

    def test_missing(self):
        class Obj:
            pass
        assert _resolve_territorio_id(Obj(), "territorio_id") is None


class TestUserProfile:
    def test_create(self, role_adt, territory_rn):
        profile = UserProfileFactory(perfil=role_adt, territorio=territory_rn)
        assert profile.perfil == role_adt
        assert profile.territorio == territory_rn

    def test_global_when_territory_null(self, role_ugp):
        profile = UserProfileFactory(perfil=role_ugp, territorio=None)
        assert profile.territorio is None

    def test_str(self, role_adt, territory_rn):
        profile = UserProfileFactory(perfil=role_adt, territorio=territory_rn)
        assert str(role_adt) in str(profile)
