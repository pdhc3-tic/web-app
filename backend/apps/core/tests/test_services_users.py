import pytest
from apps.core.services.users import create_user, update_user
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory
from apps.core.models.user_profile import UserProfile


@pytest.mark.django_db
class TestCreateUser:
    def test_creates_user_with_hashed_password(self):
        user = create_user(
            email="novo@example.com",
            nome="Novo Usuário",
            password="Senha123@",
        )
        assert user.pk is not None
        assert user.check_password("Senha123@")
        assert user.password != "Senha123@"

    def test_creates_user_with_profile(self):
        role = RoleFactory(slug="ugp", nome="UGP")
        user = create_user(
            email="ugp@example.com",
            nome="UGP User",
            perfis_input=[{"perfil_id": role.pk}],
        )
        profile = UserProfile.objects.get(user=user)
        assert profile.perfil == role

    def test_creates_user_with_territories(self):
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        role = RoleFactory()
        user = create_user(
            email="art@example.com",
            nome="Articulador",
            perfis_input=[
                {"perfil_id": role.pk, "territorio_id": t1.pk},
                {"perfil_id": role.pk, "territorio_id": t2.pk},
            ],
        )
        profile_ids = set(
            UserProfile.objects.filter(user=user)
            .values_list("territorio_id", flat=True)
        )
        assert profile_ids == {t1.pk, t2.pk}

    def test_creates_user_without_password(self):
        user = create_user(email="nopass@example.com", nome="Sem Senha")
        assert user.pk is not None
        assert not user.check_password("")


@pytest.mark.django_db
class TestUpdateUser:
    def test_updates_scalar_fields(self):
        user = UserFactory(nome="Antigo")
        updated = update_user(user, nome="Novo")
        assert updated.nome == "Novo"
        user.refresh_from_db()
        assert user.nome == "Novo"

    def test_updates_password(self):
        user = UserFactory()
        user.set_password("SenhaAntiga1!")
        user.save()

        update_user(user, password="SenhaNova2@")
        user.refresh_from_db()
        assert user.check_password("SenhaNova2@")
        assert not user.check_password("SenhaAntiga1!")

    def test_updates_profiles(self):
        t1 = TerritoryFactory()
        t2 = TerritoryFactory()
        role = RoleFactory()
        user = UserFactory()
        UserProfile.objects.create(user=user, perfil=role, territorio=t1)

        update_user(
            user,
            perfis_input=[{"perfil_id": role.pk, "territorio_id": t2.pk}],
        )
        profile = UserProfile.objects.get(user=user)
        assert profile.territorio_id == t2.pk

    def test_none_profiles_does_not_clear(self):
        t1 = TerritoryFactory()
        role = RoleFactory()
        user = UserFactory()
        UserProfile.objects.create(user=user, perfil=role, territorio=t1)

        update_user(user, perfis_input=None, nome="Atualizado")
        assert UserProfile.objects.filter(user=user).count() == 1
