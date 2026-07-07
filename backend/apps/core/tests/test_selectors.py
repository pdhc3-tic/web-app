"""
Testes unitários para apps/core/selectors.py
"""
import pytest
from apps.core.selectors import organization_list
from apps.core.tests.factories import RoleFactory, UserFactory, TerritoryFactory, OrganizationFactory


@pytest.mark.django_db
class TestOrganizationList:
    def test_admin_sees_all_active(self):
        """Super-admin vê todas as organizações ativas."""
        role = RoleFactory(slug="super-admin", nome="Super Admin")
        user = UserFactory(role=role)
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=True)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="list")
        assert qs.count() == 2

    def test_list_excludes_inactive(self):
        """Na ação list, organizações inativas ficam fora."""
        role = RoleFactory(slug="super-admin", nome="Super Admin")
        user = UserFactory(role=role)
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=False)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="list")
        assert qs.count() == 1
        assert qs.first().ativa is True

    def test_retrieve_includes_inactive_for_admin(self):
        """Na ação retrieve, admin vê também inativas."""
        role = RoleFactory(slug="super-admin", nome="Super Admin")
        user = UserFactory(role=role)
        t = TerritoryFactory()
        o1 = OrganizationFactory(ativa=True)
        o2 = OrganizationFactory(ativa=False)
        o1.territorios.set([t])
        o2.territorios.set([t])

        qs = organization_list(user, action="retrieve")
        assert qs.count() == 2

    def test_articulador_sees_only_own_territory(self):
        """Articulador vê apenas organizações dos seus territórios, sempre ativas."""
        role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        user = UserFactory(role=role)
        user.territorios.set([t1])

        o_visible = OrganizationFactory(ativa=True)
        o_other = OrganizationFactory(ativa=True)
        o_inactive = OrganizationFactory(ativa=False)
        o_visible.territorios.set([t1])
        o_other.territorios.set([t2])
        o_inactive.territorios.set([t1])

        qs = organization_list(user, action="list")
        assert qs.count() == 1
        assert qs.first().pk == o_visible.pk
