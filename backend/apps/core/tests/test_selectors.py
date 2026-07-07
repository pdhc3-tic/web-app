import pytest
from apps.core.selectors import organization_list
from apps.core.tests.factories import RoleFactory, UserFactory, TerritoryFactory, OrganizationFactory
from apps.core.models.user_profile import UserProfile


@pytest.mark.django_db
class TestOrganizationList:
    def _make_admin_user(self):
        role = RoleFactory(slug="super-admin", nome="Super Admin")
        user = UserFactory()
        UserProfile.objects.create(user=user, perfil=role)
        return user

    def _make_articulador_user(self, territory):
        role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
        user = UserFactory()
        UserProfile.objects.create(user=user, perfil=role, territorio=territory)
        return user

    def test_admin_sees_all_active(self):
        user = self._make_admin_user()
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=True)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="list")
        assert qs.count() == 2

    def test_list_excludes_inactive(self):
        user = self._make_admin_user()
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=False)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="list")
        assert qs.count() == 1
        assert qs.first().ativa is True

    def test_retrieve_includes_inactive_for_admin(self):
        user = self._make_admin_user()
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=False)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="retrieve")
        assert qs.count() == 2

    def test_articulador_sees_only_own_territory(self):
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        user = self._make_articulador_user(t1)

        o_visible = OrganizationFactory(ativa=True)
        o_other = OrganizationFactory(ativa=True)
        o_inactive = OrganizationFactory(ativa=False)
        o_visible.territorios.set([t1])
        o_other.territorios.set([t2])
        o_inactive.territorios.set([t1])

        qs = organization_list(user, action="list")
        assert qs.count() == 1
        assert qs.first().pk == o_visible.pk
