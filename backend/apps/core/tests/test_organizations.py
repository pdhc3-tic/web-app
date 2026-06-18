import pytest
from rest_framework.test import APIClient

from apps.core.models import Organization, Municipality, State, Territory, Role, User
from apps.core.models.user_profile import UserProfile
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory, UserProfileFactory

pytestmark = pytest.mark.django_db


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

VALID_CNPJ = "11222333000181"  # CNPJ válido (verificável via algoritmo)
VALID_CNPJ_2 = "11444777000161"  # Segundo CNPJ válido


@pytest.fixture
def state_rn():
    return State.objects.get_or_create(sigla="RN", defaults={"nome": "Rio Grande do Norte"})[0]


@pytest.fixture
def state_pb():
    return State.objects.get_or_create(sigla="PB", defaults={"nome": "Paraíba"})[0]


@pytest.fixture
def municipality(state_rn):
    return Municipality.objects.create(
        nome="Mossoró",
        state=state_rn,
        codigo_ibge="2408003",
    )


@pytest.fixture
def territory_a():
    return TerritoryFactory(nome="Território A", estados=["RN"])


@pytest.fixture
def territory_b():
    return TerritoryFactory(nome="Território B", estados=["PB"])


@pytest.fixture
def territory_c():
    return TerritoryFactory(nome="Território C", estados=["CE"])


@pytest.fixture
def role_super_admin():
    return Role.objects.get_or_create(slug="super-admin", defaults={"nome": "Super Admin"})[0]


@pytest.fixture
def role_ugp():
    return Role.objects.get_or_create(slug="ugp", defaults={"nome": "UGP"})[0]


@pytest.fixture
def role_articulador():
    return Role.objects.get_or_create(slug="articulador-estadual", defaults={"nome": "Articulador Estadual"})[0]


@pytest.fixture
def role_adt():
    return Role.objects.get_or_create(slug="adt-acr", defaults={"nome": "ADT / ACR"})[0]


@pytest.fixture
def super_admin_client(role_super_admin):
    user = UserFactory()
    UserProfile.objects.create(user=user, perfil=role_super_admin)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def ugp_client(role_ugp):
    user = UserFactory()
    UserProfile.objects.create(user=user, perfil=role_ugp)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def articulador_client(role_articulador, territory_a):
    user = UserFactory()
    UserProfile.objects.create(user=user, perfil=role_articulador, territorio=territory_a)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def adt_client(role_adt):
    user = UserFactory()
    UserProfile.objects.create(user=user, perfil=role_adt)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org_payload(municipality):
    """Payload base para criação de organização."""
    return {
        "nome": "OSC Teste",
        "cnpj": VALID_CNPJ,
        "tipo": "ASSOCIACAO",
        "municipio": municipality.pk,
        "contato": "João Silva",
        "email": "contato@osc.org.br",
        "telefone": "(84) 99999-0000",
    }


URL = "/api/v1/organizations/"


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


class TestCreateOrganizationValidCnpj:
    """POST com CNPJ válido cria a OSC e retorna 201."""

    def test_create_organization_valid_cnpj(self, super_admin_client, org_payload):
        response = super_admin_client.post(URL, org_payload, format="json")
        assert response.status_code == 201
        assert Organization.objects.filter(cnpj=VALID_CNPJ).exists()
        assert response.data["nome"] == "OSC Teste"
        assert response.data["cnpj"] == VALID_CNPJ


class TestCreateOrganizationInvalidCnpjReturns400:
    """CNPJ '12345678901234' (inválido) retorna 400 com erro de validação."""

    def test_create_organization_invalid_cnpj_returns_400(self, super_admin_client, org_payload):
        org_payload["cnpj"] = "12345678901234"
        response = super_admin_client.post(URL, org_payload, format="json")
        assert response.status_code == 400
        assert "CNPJ inválido" in str(response.data)


class TestCreateOrganizationDuplicateCnpjReturns400:
    """Segundo POST com mesmo CNPJ retorna 400."""

    def test_create_organization_duplicate_cnpj_returns_400(
        self, super_admin_client, org_payload, municipality
    ):
        # Primeiro POST — deve funcionar
        response1 = super_admin_client.post(URL, org_payload, format="json")
        assert response1.status_code == 201

        # Segundo POST com mesmo CNPJ — deve falhar
        org_payload["nome"] = "OSC Duplicada"
        response2 = super_admin_client.post(URL, org_payload, format="json")
        assert response2.status_code == 400
        assert "Já existe uma organização cadastrada com este CNPJ" in str(response2.data)



class TestOrganizationMultiTerritoryAssignment:
    """POST com territorios=[a, b, c] cria os três vínculos M2M."""

    def test_organization_multi_territory_assignment(
        self, super_admin_client, org_payload, territory_a, territory_b, territory_c
    ):
        org_payload["territorios"] = [territory_a.pk, territory_b.pk, territory_c.pk]
        response = super_admin_client.post(URL, org_payload, format="json")
        assert response.status_code == 201

        org = Organization.objects.get(pk=response.data["id"])
        assert org.territorios.count() == 3
        assert set(org.territorios.values_list("pk", flat=True)) == {
            territory_a.pk, territory_b.pk, territory_c.pk,
        }


class TestSuperAdminSeesAllOrganizations:
    """Super Admin lista todas as OSCs ativas."""

    def test_super_admin_sees_all_organizations(
        self, super_admin_client, municipality, territory_a, territory_b
    ):
        org1 = Organization.objects.create(
            nome="OSC Alpha", cnpj=VALID_CNPJ, tipo="ASSOCIACAO", municipio=municipality
        )
        org1.territorios.add(territory_a)
        org2 = Organization.objects.create(
            nome="OSC Beta", cnpj=VALID_CNPJ_2, tipo="COOPERATIVA", municipio=municipality
        )
        org2.territorios.add(territory_b)

        response = super_admin_client.get(URL)
        assert response.status_code == 200
        names = {r["nome"] for r in response.data["results"]}
        assert "OSC Alpha" in names
        assert "OSC Beta" in names


class TestArticuladorSeesOnlyOwnTerritoryOrganizations:
    """Articulador do território A vê OSCs com territorio A; não vê OSCs do território B."""

    def test_articulador_sees_only_own_territory_organizations(
        self, articulador_client, municipality, territory_a, territory_b
    ):
        # OSC no território A (visível)
        org_visible = Organization.objects.create(
            nome="OSC Visível", cnpj=VALID_CNPJ, tipo="ASSOCIACAO", municipio=municipality
        )
        org_visible.territorios.add(territory_a)

        # OSC no território B (invisível para o articulador)
        org_hidden = Organization.objects.create(
            nome="OSC Oculta", cnpj=VALID_CNPJ_2, tipo="FUNDACAO", municipio=municipality
        )
        org_hidden.territorios.add(territory_b)

        response = articulador_client.get(URL)
        assert response.status_code == 200
        names = {r["nome"] for r in response.data["results"]}
        assert "OSC Visível" in names
        assert "OSC Oculta" not in names


class TestAdtCannotAccessOrganizations:
    """ADT recebe 403 em GET, POST, PATCH, DELETE."""

    def test_adt_cannot_access_organizations(self, adt_client, municipality, org_payload):
        # Cria OSC para testar PATCH e DELETE
        org = Organization.objects.create(
            nome="OSC ADT Test", cnpj=VALID_CNPJ, tipo="OUTRO", municipio=municipality
        )

        assert adt_client.get(URL).status_code == 403
        assert adt_client.post(URL, org_payload, format="json").status_code == 403
        assert adt_client.patch(f"{URL}{org.pk}/", {"nome": "Hacked"}, format="json").status_code == 403
        assert adt_client.delete(f"{URL}{org.pk}/").status_code == 403


class TestSoftDeleteKeepsRecord:
    """DELETE marca ativa=False; OSC desaparece da listagem mas continua no banco."""

    def test_soft_delete_keeps_record(self, super_admin_client, municipality):
        org = Organization.objects.create(
            nome="OSC Soft Delete", cnpj=VALID_CNPJ, tipo="ASSOCIACAO", municipio=municipality
        )

        # DELETE — soft delete
        response = super_admin_client.delete(f"{URL}{org.pk}/")
        assert response.status_code == 204

        # Registro ainda existe no banco
        org.refresh_from_db()
        assert org.ativa is False

        # Não aparece na listagem padrão
        list_response = super_admin_client.get(URL)
        org_ids = [r["id"] for r in list_response.data["results"]]
        assert org.pk not in org_ids
