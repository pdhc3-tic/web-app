"""Busca de atividades para vincular a uma demanda: sem o recorte territorial do SGP,
só Planejado e Agendado, aberta a quem cria demanda."""
import pytest

from apps.core.tests.factories import MunicipalityFactory, RoleFactory, StateFactory, TerritoryFactory, UserFactory
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/atividades-elegiveis/"


@pytest.fixture
def adt_pb(db):
    territorio = TerritoryFactory(nome="Território PB", estados=["PB"])
    return UserFactory(
        email="adt.pb@test.com", nome="ADT PB", profiles=[(RoleFactory(slug="adt-acr", nome="ADT / ACR"), territorio)],
    )


@pytest.fixture
def municipio_rn(db):
    return MunicipalityFactory(
        nome="Mossoró", state=StateFactory(sigla="RN", nome="Rio Grande do Norte"),
        territory=TerritoryFactory(nome="Território RN", estados=["RN"]), codigo_ibge="2408003",
    )


@pytest.fixture
def client_adt_pb(api_client, adt_pb):
    api_client.force_authenticate(user=adt_pb)
    return api_client


def _ids(resp):
    return [item["id"] for item in resp.data["results"]]


def test_adt_da_pb_encontra_atividade_do_rn(client_adt_pb, municipio_rn):
    tecnico = UserFactory(nome="Técnica RN")
    atividade = ActivityFactory(municipio=municipio_rn, tecnico_responsavel=tecnico, titulo="Feira em Mossoró")

    resp = client_adt_pb.get(URL)

    assert resp.status_code == 200, resp.data
    assert resp.data["results"] == [{
        "id": atividade.pk, "titulo": "Feira em Mossoró", "status": "planejado", "status_display": "Planejado",
        "data_inicio": resp.data["results"][0]["data_inicio"], "data_fim": resp.data["results"][0]["data_fim"],
        "municipio": {
            "id": municipio_rn.pk, "nome": "Mossoró",
            "estado": {"id": municipio_rn.state_id, "sigla": "RN", "nome": "Rio Grande do Norte"},
        },
        "tecnico_responsavel": tecnico.pk, "tecnico_nome": "Técnica RN",
    }]


def test_so_planejado_e_agendado(client_adt_pb, municipio_rn):
    elegiveis = [
        ActivityFactory(municipio=municipio_rn, status="planejado").pk,
        ActivityFactory(municipio=municipio_rn, status="agendado").pk,
    ]
    for status in ("em_andamento", "adiada", "cancelada", "nao_realizada", "concluido"):
        ActivityFactory(municipio=municipio_rn, status=status)
    ActivityFactory(municipio=municipio_rn, status="planejado", ativo=False)

    resp = client_adt_pb.get(URL)

    assert sorted(_ids(resp)) == sorted(elegiveis)


def test_filtro_de_status_restringe_as_elegiveis(client_adt_pb, municipio_rn):
    ActivityFactory(municipio=municipio_rn, status="planejado")
    agendada = ActivityFactory(municipio=municipio_rn, status="agendado")

    resp = client_adt_pb.get(URL, {"status": "agendado"})

    assert _ids(resp) == [agendada.pk]


@pytest.mark.parametrize("status", ["em_andamento", "cancelada", "qualquer"])
def test_status_fora_das_elegiveis_e_400(client_adt_pb, status):
    resp = client_adt_pb.get(URL, {"status": ["planejado", status]})

    assert resp.status_code == 400
    assert "status" in resp.data


def test_busca_pelo_titulo(client_adt_pb, municipio_rn):
    feira = ActivityFactory(municipio=municipio_rn, titulo="Feira Agroecológica")
    ActivityFactory(municipio=municipio_rn, titulo="Oficina de Sementes")

    resp = client_adt_pb.get(URL, {"q": "  agroecol "})

    assert _ids(resp) == [feira.pk]


def test_paginacao_igual_a_da_listagem_do_sgp(client_adt_pb, municipio_rn):
    for _ in range(3):
        ActivityFactory(municipio=municipio_rn)

    resp = client_adt_pb.get(URL, {"page_size": 2})

    assert resp.data["count"] == 3
    assert len(resp.data["results"]) == 2
    assert resp.data["next"] is not None


def test_super_admin_tambem_busca(auth_client_super_admin, municipio_rn):
    atividade = ActivityFactory(municipio=municipio_rn)

    resp = auth_client_super_admin.get(URL)

    assert resp.status_code == 200
    assert _ids(resp) == [atividade.pk]


@pytest.mark.parametrize("cliente", ["auth_client_articulador_rn", "auth_client_ugp", "auth_client_fgd"])
def test_quem_nao_cria_demanda_recebe_403(request, cliente):
    resp = request.getfixturevalue(cliente).get(URL)

    assert resp.status_code == 403


def test_sem_autenticacao_recebe_401(api_client):
    assert api_client.get(URL).status_code == 401
