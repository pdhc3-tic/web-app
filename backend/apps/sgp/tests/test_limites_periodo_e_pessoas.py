"""Período dos limites e lista das pessoas que recebem limite individual."""
import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time

from apps.core.models.system_config import SystemConfig
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory

pytestmark = pytest.mark.django_db

PERIODO_URL = "/api/v1/sgp/orcamento/limites/periodo/"
PESSOAS_URL = "/api/v1/sgp/orcamento/limites/pessoas/"


def _periodicidade(valor):
    SystemConfig.objects.filter(chave="budget_limit_period").update(valor=valor)
    cache.delete("system_config:budget_limit_period")


@freeze_time("2026-11-17")
class TestPeriodo:
    @pytest.mark.parametrize("periodicidade, inicio, fim", [
        ("mensal", "2026-11-01", "2026-11-30"),
        ("trimestral", "2026-10-01", "2026-12-31"),
        ("semestral", "2026-07-01", "2026-12-31"),
        ("vigencia", "2000-01-01", "2099-12-31"),
    ])
    def test_devolve_o_periodo_de_hoje(self, auth_client, periodicidade, inicio, fim):
        _periodicidade(periodicidade)

        resposta = auth_client.get(PERIODO_URL)

        assert resposta.status_code == 200
        assert resposta.json() == {"inicio": inicio, "fim": fim, "periodicidade": periodicidade}

    def test_devolve_o_periodo_da_data_pedida(self, auth_client):
        _periodicidade("trimestral")

        resposta = auth_client.get(PERIODO_URL, {"data": "2027-02-10"})

        assert resposta.json() == {"inicio": "2027-01-01", "fim": "2027-03-31", "periodicidade": "trimestral"}

    def test_periodicidade_desconhecida_conta_como_trimestral(self, auth_client):
        _periodicidade("anual")

        assert auth_client.get(PERIODO_URL).json()["periodicidade"] == "trimestral"

    def test_data_invalida_e_400(self, auth_client):
        assert auth_client.get(PERIODO_URL, {"data": "ontem"}).status_code == 400

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_articulador_rn", "auth_client_fgd"])
    def test_so_ugp_e_super_admin(self, request, cliente):
        assert request.getfixturevalue(cliente).get(PERIODO_URL).status_code == 403


class TestPessoas:
    @pytest.fixture
    def pessoas(self, db):
        tecnico = RoleFactory(slug="adt-acr", nome="ADT / ACR")
        articulador = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
        ugp = RoleFactory(slug="ugp", nome="UGP")
        territorio = TerritoryFactory()
        return {
            "ana": UserFactory(nome="Ana Técnica", email="ana@test.com", profiles=[(tecnico, territorio)]),
            "bruno": UserFactory(
                nome="Bruno Duplo", email="bruno@test.com",
                profiles=[(articulador, territorio), (tecnico, territorio), (tecnico, TerritoryFactory())],
            ),
            "carla": UserFactory(nome="Carla Articuladora", email="carla@test.com", profiles=[(articulador, None)]),
            "inativo": UserFactory(
                nome="Davi Inativo", email="davi@test.com", ativo=False, profiles=[(tecnico, territorio)],
            ),
            "ugp": UserFactory(nome="Elisa UGP", email="elisa@test.com", profiles=[(ugp, None)]),
        }

    def test_lista_os_ativos_com_adt_acr_ou_articulador_ordenados_por_nome(self, auth_client, pessoas):
        resposta = auth_client.get(PESSOAS_URL)

        assert resposta.status_code == 200
        assert resposta.json() == [
            {"id": pessoas["ana"].pk, "nome": "Ana Técnica", "perfis": [{"slug": "adt-acr", "nome": "ADT / ACR"}]},
            {"id": pessoas["bruno"].pk, "nome": "Bruno Duplo", "perfis": [
                {"slug": "adt-acr", "nome": "ADT / ACR"},
                {"slug": "articulador-estadual", "nome": "Articulador Estadual"},
            ]},
            {"id": pessoas["carla"].pk, "nome": "Carla Articuladora", "perfis": [
                {"slug": "articulador-estadual", "nome": "Articulador Estadual"},
            ]},
        ]

    @pytest.mark.parametrize("busca, esperados", [("bru", ["bruno"]), ("CARLA@", ["carla"]), ("davi", [])])
    def test_busca_por_nome_ou_email(self, auth_client, pessoas, busca, esperados):
        resposta = auth_client.get(PESSOAS_URL, {"q": busca})

        assert [item["id"] for item in resposta.json()] == [pessoas[chave].pk for chave in esperados]

    def test_consultas_nao_crescem_com_o_numero_de_pessoas(self, auth_client, pessoas):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                auth_client.get(PESSOAS_URL)
            return len(capturadas)

        consultas()  # O primeiro pedido aquece o cache dos parâmetros.
        antes = consultas()
        tecnico = RoleFactory(slug="adt-acr")
        for i in range(10):
            UserFactory(nome=f"Extra {i}", profiles=[(tecnico, TerritoryFactory())])

        assert consultas() == antes

    def test_super_admin_tambem_acessa(self, auth_client_super_admin, pessoas):
        assert auth_client_super_admin.get(PESSOAS_URL).status_code == 200

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_articulador_rn", "auth_client_fgd"])
    def test_outros_perfis_recebem_403(self, request, cliente):
        assert request.getfixturevalue(cliente).get(PESSOAS_URL).status_code == 403
