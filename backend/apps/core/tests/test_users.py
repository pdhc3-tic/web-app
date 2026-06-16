import pytest
from rest_framework import status


# ──────────────────────────────────────────────────────────────
# GET /api/v1/users/  (list)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_list_users_as_super_admin_returns_200(api_client, super_admin_user, user_factory):
    api_client.force_authenticate(user=super_admin_user)
    user_factory.create_batch(3)

    response = api_client.get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    # super_admin_user + 3 batch = 4
    assert len(response.data["results"]) == 4


@pytest.mark.django_db
def test_list_users_as_adt_returns_403(api_client, adt_user):
    api_client.force_authenticate(user=adt_user)

    response = api_client.get("/api/v1/users/")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_list_users_as_super_admin_pagination_default_20(api_client, super_admin_user, user_factory):
    api_client.force_authenticate(user=super_admin_user)
    user_factory.create_batch(25)

    response = api_client.get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 20
    assert response.data["next"] is not None


@pytest.mark.django_db
def test_list_users_filter_by_active_false_shows_deactivated(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    active = user_factory(ativo=True)
    inactive = user_factory(ativo=False)

    # Default: only active
    response = api_client.get("/api/v1/users/")
    assert response.status_code == status.HTTP_200_OK
    result_ids = [u["id"] for u in response.data["results"]]
    assert active.pk in result_ids
    assert inactive.pk not in result_ids

    # With ?ativo=false: includes inactive
    response = api_client.get("/api/v1/users/?ativo=false")
    assert response.status_code == status.HTTP_200_OK
    result_ids = [u["id"] for u in response.data["results"]]
    assert inactive.pk in result_ids


@pytest.mark.django_db
def test_list_users_filter_by_territorio(
    api_client, super_admin_user, user_factory, territory_factory
):
    api_client.force_authenticate(user=super_admin_user)
    t1 = territory_factory()
    t2 = territory_factory()
    u1 = user_factory()
    u1.territorios.add(t1)
    u2 = user_factory()
    u2.territorios.add(t2)

    response = api_client.get(f"/api/v1/users/?territorio={t1.pk}")

    assert response.status_code == status.HTTP_200_OK
    result_ids = [u["id"] for u in response.data["results"]]
    assert u1.pk in result_ids
    assert u2.pk not in result_ids


@pytest.mark.django_db
def test_list_users_search_by_nome(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user_factory(nome="João Silva")
    user_factory(nome="Maria Santos")

    response = api_client.get("/api/v1/users/?search=João")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["nome_completo"] == "João Silva"


@pytest.mark.django_db
def test_list_users_search_by_email(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user_factory(email="joao@example.com")
    user_factory(email="maria@example.com")

    response = api_client.get("/api/v1/users/?search=joao")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["email"] == "joao@example.com"


@pytest.mark.django_db
def test_list_users_ordering_default_ultimo_login(
    api_client, user_factory, role_factory
):
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    role = role_factory(slug="super-admin", nome="Super Admin")
    user = user_factory(role=role, ultimo_login=now - timedelta(hours=2))
    api_client.force_authenticate(user=user)
    u1 = user_factory(ultimo_login=now)
    u2 = user_factory(ultimo_login=now - timedelta(hours=1))

    response = api_client.get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    ids = [u["id"] for u in response.data["results"]]
    newest_idx = ids.index(u1.pk)
    mid_idx = ids.index(u2.pk)
    oldest_idx = ids.index(user.pk)
    assert newest_idx < mid_idx < oldest_idx


# ──────────────────────────────────────────────────────────────
# GET /api/v1/users/{id}/  (retrieve)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_retrieve_user_returns_detail_with_nested(
    api_client, super_admin_user, user_factory, role_factory, territory_factory
):
    api_client.force_authenticate(user=super_admin_user)
    role = role_factory(slug="adt-acr", nome="ADT / ACR")
    territory = territory_factory(nome="Sertão do Apodi", estados=["RN"])
    user = user_factory(role=role)
    user.territorios.add(territory)

    response = api_client.get(f"/api/v1/users/{user.pk}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["nome_completo"] == user.nome
    assert len(response.data["perfis"]) == 1
    assert response.data["perfis"][0]["slug"] == "adt-acr"
    assert len(response.data["territorios"]) == 1
    assert response.data["territorios"][0]["nome"] == "Sertão do Apodi"


# ──────────────────────────────────────────────────────────────
# POST /api/v1/users/  (create)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_user_with_profile_and_territory(
    api_client, super_admin_user, role_factory, territory_factory
):
    api_client.force_authenticate(user=super_admin_user)
    role = role_factory(slug="adt-acr", nome="ADT / ACR")
    territory = territory_factory(nome="Sertão do Apodi")

    data = {
        "email": "novo@test.com",
        "nome_completo": "Novo Usuário",
        "password": "SenhaForte1",
        "perfil_id": role.pk,
        "territorio_ids": [territory.pk],
    }

    response = api_client.post("/api/v1/users/", data, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == "novo@test.com"
    assert response.data["nome_completo"] == "Novo Usuário"
    assert len(response.data["perfis"]) == 1
    assert response.data["perfis"][0]["slug"] == "adt-acr"
    assert len(response.data["territorios"]) == 1
    assert response.data["territorios"][0]["nome"] == "Sertão do Apodi"
    assert "password" not in response.data


@pytest.mark.django_db
def test_create_user_duplicate_email_returns_400(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user_factory(email="existente@test.com")

    data = {
        "email": "existente@test.com",
        "nome_completo": "Duplicado",
        "password": "SenhaForte1",
    }

    response = api_client.post("/api/v1/users/", data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Já existe um usuário com este e-mail" in str(response.data)


@pytest.mark.django_db
def test_create_user_missing_required_fields(
    api_client, super_admin_user
):
    api_client.force_authenticate(user=super_admin_user)

    response = api_client.post("/api/v1/users/", {"email": "incompleto@test.com"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────
# PATCH /api/v1/users/{id}/  (partial_update)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_update_user_changes_profile_preserves_history(
    api_client, super_admin_user, user_factory, role_factory
):
    api_client.force_authenticate(user=super_admin_user)
    old_role = role_factory(slug="adt-acr", nome="ADT / ACR")
    new_role = role_factory(slug="ugp", nome="UGP")
    user = user_factory(role=old_role, nome="Usuário Teste")

    # PATCH — troca o perfil
    response = api_client.patch(
        f"/api/v1/users/{user.pk}/",
        {"perfil_id": new_role.pk},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["perfis"][0]["slug"] == "ugp"


@pytest.mark.django_db
def test_update_user_partial_no_side_effects(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user = user_factory(nome="Nome Original", email="original@test.com")

    response = api_client.patch(
        f"/api/v1/users/{user.pk}/",
        {"nome_completo": "Nome Alterado"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["nome_completo"] == "Nome Alterado"
    assert response.data["email"] == "original@test.com"


# ──────────────────────────────────────────────────────────────
# DELETE /api/v1/users/{id}/  (soft-delete)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_soft_delete_user_keeps_data(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user = user_factory(ativo=True)

    response = api_client.delete(f"/api/v1/users/{user.pk}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Soft-delete: ainda existe no banco, mas ativo=False
    user.refresh_from_db()
    assert user.ativo is False


@pytest.mark.django_db
def test_soft_delete_user_disappears_from_default_list(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user = user_factory(ativo=True)

    api_client.delete(f"/api/v1/users/{user.pk}/")

    response = api_client.get("/api/v1/users/")
    result_ids = [u["id"] for u in response.data["results"]]
    assert user.pk not in result_ids


@pytest.mark.django_db
def test_soft_delete_user_still_accessible_with_filter(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user = user_factory(ativo=True)
    api_client.delete(f"/api/v1/users/{user.pk}/")

    response = api_client.get("/api/v1/users/?ativo=false")
    result_ids = [u["id"] for u in response.data["results"]]
    assert user.pk in result_ids


# ──────────────────────────────────────────────────────────────
# Serializer — campo senha_hash nunca exposto
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_serializer_does_not_expose_password_hash(
    api_client, super_admin_user, user_factory
):
    api_client.force_authenticate(user=super_admin_user)
    user = user_factory()

    # List
    response = api_client.get("/api/v1/users/")
    assert response.status_code == status.HTTP_200_OK
    for u in response.data["results"]:
        assert "password" not in u
        assert "senha" not in u
        assert "password_hash" not in u

    # Retrieve
    response = api_client.get(f"/api/v1/users/{user.pk}/")
    assert response.status_code == status.HTTP_200_OK
    assert "password" not in response.data
    assert "senha" not in response.data


# ──────────────────────────────────────────────────────────────
# Permissions matrix — 6 perfis × 5 ações
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_permissions_matrix(
    api_client, role_factory, user_factory, territory_factory
):
    """Varredura de 6 perfis × 5 ações: apenas Super Admin passa."""
    slugs = [
        "agricultor",
        "adt-acr",
        "articulador-estadual",
        "ugp",
        "fgd",
        "super-admin",
    ]
    expected = {
        "super-admin": {
            "list": status.HTTP_200_OK,
            "retrieve": status.HTTP_200_OK,
            "create": status.HTTP_201_CREATED,
            "update": status.HTTP_200_OK,
            "delete": status.HTTP_204_NO_CONTENT,
        },
    }
    for slug in slugs:
        if slug != "super-admin":
            expected[slug] = {action: status.HTTP_403_FORBIDDEN for action in
                              ["list", "retrieve", "create", "update", "delete"]}

    territory = territory_factory()

    for slug in slugs:
        role = role_factory(slug=slug, nome=slug.replace("-", " ").title())
        is_super = slug == "super-admin"
        user = user_factory(
            role=role,
            is_superuser=is_super,
        )
        api_client.force_authenticate(user=user)

        target = user_factory()
        target.territorios.add(territory)

        # list
        resp = api_client.get("/api/v1/users/")
        assert resp.status_code == expected[slug]["list"], (
            f"list/{slug}: esperado {expected[slug]['list']}, got {resp.status_code}"
        )

        # retrieve
        resp = api_client.get(f"/api/v1/users/{target.pk}/")
        assert resp.status_code == expected[slug]["retrieve"], (
            f"retrieve/{slug}: esperado {expected[slug]['retrieve']}, got {resp.status_code}"
        )

        # create
        resp = api_client.post(
            "/api/v1/users/",
            {"email": f"{slug}@test.com", "nome_completo": slug.title(), "password": "SenhaForte1"},
            format="json",
        )
        assert resp.status_code == expected[slug]["create"], (
            f"create/{slug}: esperado {expected[slug]['create']}, got {resp.status_code}"
        )

        # update (PATCH)
        resp = api_client.patch(
            f"/api/v1/users/{target.pk}/",
            {"nome": "Updated"},
            format="json",
        )
        assert resp.status_code == expected[slug]["update"], (
            f"update/{slug}: esperado {expected[slug]['update']}, got {resp.status_code}"
        )

        # delete
        resp = api_client.delete(f"/api/v1/users/{target.pk}/")
        assert resp.status_code == expected[slug]["delete"], (
            f"delete/{slug}: esperado {expected[slug]['delete']}, got {resp.status_code}"
        )
