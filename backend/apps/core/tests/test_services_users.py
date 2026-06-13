"""
Testes unitários para apps/core/services/users.py
"""
import pytest
from apps.core.services.users import create_user, update_user
from apps.core.tests.factories import RoleFactory, TerritoryFactory


@pytest.mark.django_db
class TestCreateUser:
    def test_creates_user_with_hashed_password(self):
        """Senha em texto plano é hasheada corretamente."""
        user = create_user(
            email="novo@example.com",
            nome="Novo Usuário",
            password="Senha123@",
        )
        assert user.pk is not None
        assert user.check_password("Senha123@")
        assert user.password != "Senha123@"

    def test_creates_user_with_role(self):
        """Role é atribuído corretamente."""
        role = RoleFactory(slug="ugp", nome="UGP")
        user = create_user(email="ugp@example.com", nome="UGP User", role=role)
        assert user.role == role

    def test_creates_user_with_territories(self):
        """Territórios são vinculados via M2M."""
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        user = create_user(
            email="art@example.com",
            nome="Articulador",
            territorios=[t1, t2],
        )
        assert set(user.territorios.values_list("pk", flat=True)) == {t1.pk, t2.pk}

    def test_creates_user_without_password(self):
        """Sem senha, o usuário é criado mas não pode autenticar."""
        user = create_user(email="nopass@example.com", nome="Sem Senha")
        assert user.pk is not None
        assert not user.check_password("")


@pytest.mark.django_db
class TestUpdateUser:
    def test_updates_scalar_fields(self):
        """Campos escalares são atualizados corretamente."""
        from apps.core.tests.factories import UserFactory
        user = UserFactory(nome="Antigo")
        updated = update_user(user, nome="Novo")
        assert updated.nome == "Novo"
        user.refresh_from_db()
        assert user.nome == "Novo"

    def test_updates_password(self):
        """Senha nova é hasheada e a anterior fica inválida."""
        from apps.core.tests.factories import UserFactory
        user = UserFactory()
        user.set_password("SenhaAntiga1!")
        user.save()

        update_user(user, password="SenhaNova2@")
        user.refresh_from_db()
        assert user.check_password("SenhaNova2@")
        assert not user.check_password("SenhaAntiga1!")

    def test_updates_territories(self):
        """Territórios são substituídos via set()."""
        from apps.core.tests.factories import UserFactory
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        user = UserFactory()
        user.territorios.set([t1])

        update_user(user, territorios=[t2])
        assert list(user.territorios.values_list("pk", flat=True)) == [t2.pk]

    def test_none_territories_does_not_clear(self):
        """Passar territorios=None não limpa o M2M."""
        from apps.core.tests.factories import UserFactory
        t1 = TerritoryFactory()
        user = UserFactory()
        user.territorios.set([t1])

        update_user(user, territorios=None, nome="Atualizado")
        assert user.territorios.count() == 1
