import pytest

from apps.sgp.models import BudgetRubrica
from apps.sgp.tests.factories import BudgetRubricaFactory

pytestmark = pytest.mark.django_db

RUBRICAS_URL = "/api/v1/sgp/rubricas/"


@pytest.fixture
def rubrica_inativa():
    return BudgetRubricaFactory(nome="Aaa Rubrica Desativada", slug="desativada", ativo=False)


def _ids(response):
    return [rubrica["id"] for rubrica in response.data]


class TestListaDeRubricas:
    def test_lista_todas_sem_paginacao_ordenadas_por_nome(
        self, auth_client_super_admin, rubrica_inativa,
    ):
        response = auth_client_super_admin.get(RUBRICAS_URL)

        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert _ids(response) == list(
            BudgetRubrica.objects.order_by("nome", "id").values_list("id", flat=True)
        )
        assert rubrica_inativa.pk in _ids(response)

    def test_rubricas_com_o_mesmo_nome_saem_pela_ordem_do_id(self, auth_client_super_admin):
        primeira = BudgetRubricaFactory(nome="Aaa Repetida", slug="repetida-1")
        segunda = BudgetRubricaFactory(nome="Aaa Repetida", slug="repetida-2")

        response = auth_client_super_admin.get(RUBRICAS_URL)

        assert _ids(response)[:2] == [primeira.pk, segunda.pk]

    def test_cada_rubrica_traz_id_slug_nome_e_ativo(self, auth_client_super_admin, rubrica_inativa):
        response = auth_client_super_admin.get(RUBRICAS_URL)

        linha = next(rubrica for rubrica in response.data if rubrica["id"] == rubrica_inativa.pk)
        assert linha == {
            "id": rubrica_inativa.pk,
            "slug": "desativada",
            "nome": "Aaa Rubrica Desativada",
            "ativo": False,
        }

    def test_ativo_true_devolve_so_as_ativas(self, auth_client_super_admin, rubrica_inativa):
        response = auth_client_super_admin.get(f"{RUBRICAS_URL}?ativo=true")

        assert response.status_code == 200
        ativas = BudgetRubrica.objects.filter(ativo=True).order_by("nome", "id")
        assert _ids(response) == list(ativas.values_list("id", flat=True))
        assert rubrica_inativa.pk not in _ids(response)

    def test_ativo_false_devolve_so_as_inativas(self, auth_client_super_admin, rubrica_inativa):
        response = auth_client_super_admin.get(f"{RUBRICAS_URL}?ativo=false")

        assert response.status_code == 200
        assert _ids(response) == [rubrica_inativa.pk]

    def test_ativo_invalido_e_400(self, auth_client_super_admin):
        response = auth_client_super_admin.get(f"{RUBRICAS_URL}?ativo=talvez")

        assert response.status_code == 400
        assert "ativo" in response.data


class TestPermissaoDaListaDeRubricas:
    @pytest.mark.parametrize(
        "cliente",
        ["auth_client_adt_rn", "auth_client_articulador_rn", "auth_client_sem_acesso"],
    )
    def test_qualquer_usuario_autenticado_le(self, request, cliente):
        response = request.getfixturevalue(cliente).get(RUBRICAS_URL)

        assert response.status_code == 200
        assert len(response.data) == BudgetRubrica.objects.count()

    def test_anonimo_recebe_401(self, api_client):
        response = api_client.get(RUBRICAS_URL)

        assert response.status_code == 401
