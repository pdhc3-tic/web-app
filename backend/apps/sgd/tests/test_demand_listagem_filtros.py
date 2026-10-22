"""Listagem de demandas: filtro por atividade, status repetido, fila e paginação."""
import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

LISTA = "/api/v1/sgd/demandas/"
CONTAGEM = "/api/v1/sgd/demandas/aguardando-minha-acao/contagem/"


def _ids(response):
    return [d["id"] for d in response.data["results"]]


@pytest.fixture
def demandas(activity_rn, municipio_rn, solicitante_rn):
    outra_atividade = ActivityFactory(municipio=municipio_rn, tecnico_responsavel=solicitante_rn)
    return {
        "sub": DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida"),
        "aut": DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="autorizada"),
        "atend": DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="em_atendimento"),
        "pre": DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="pre_autorizada"),
        "outra": DemandFactory(activity=outra_atividade, solicitante=solicitante_rn, status="autorizada"),
    }


def test_activity_isola_demandas_de_atividades_diferentes(auth_client_ugp, demandas, activity_rn):
    ids = set(_ids(auth_client_ugp.get(LISTA, {"activity": activity_rn.pk})))

    assert demandas["outra"].pk not in ids
    assert {demandas["sub"].pk, demandas["aut"].pk} <= ids


def test_status_repetido_retorna_a_uniao(auth_client_ugp, demandas, activity_rn):
    response = auth_client_ugp.get(
        LISTA + "?status=autorizada&status=em_atendimento&activity=" + str(activity_rn.pk),
    )

    assert set(_ids(response)) == {demandas["aut"].pk, demandas["atend"].pk}


@pytest.mark.parametrize("query", ["activity=abc", "status=inexistente", "aguardando_minha_acao=talvez"])
def test_parametros_invalidos_retornam_400(auth_client_ugp, query):
    assert auth_client_ugp.get(f"{LISTA}?{query}").status_code == 400


def test_paginacao_preserva_filtros_e_ordenacao(auth_client_ugp, demandas):
    pagina1 = auth_client_ugp.get(LISTA, {"status": "autorizada", "limit": 1})
    pagina2 = auth_client_ugp.get(pagina1.data["next"])

    assert pagina1.data["count"] == 2
    assert len(_ids(pagina1)) == len(_ids(pagina2)) == 1
    assert _ids(pagina1) + _ids(pagina2) == sorted(
        [demandas["aut"].pk, demandas["outra"].pk], reverse=True,
    )


def test_fila_da_fgd_inclui_autorizada_e_em_atendimento(auth_client_fgd, demandas):
    response = auth_client_fgd.get(LISTA, {"aguardando_minha_acao": "true"})

    assert {d["status"] for d in response.data["results"]} == {"autorizada", "em_atendimento"}


@pytest.mark.parametrize("cliente", [
    "auth_client_fgd", "auth_client_ugp", "auth_client_articulador_rn", "auth_client_solicitante",
])
def test_total_da_contagem_igual_ao_count_da_fila(request, cliente, demandas):
    client = request.getfixturevalue(cliente)

    lista = client.get(LISTA, {"aguardando_minha_acao": "true"})
    contagem = client.get(CONTAGEM)

    assert lista.data["count"] == contagem.data["total"]


def test_fila_de_usuario_com_dois_perfis_e_a_uniao(api_client, demandas):
    user = UserFactory(
        email="duplo@test.com",
        profiles=[(RoleFactory(slug="ugp", nome="UGP"), None), (RoleFactory(slug="fgd", nome="FGD"), None)],
    )
    api_client.force_authenticate(user)

    lista = api_client.get(LISTA, {"aguardando_minha_acao": "true"})

    assert {d["status"] for d in lista.data["results"]} == {"pre_autorizada", "autorizada", "em_atendimento"}
    assert lista.data["count"] == api_client.get(CONTAGEM).data["total"]


@pytest.fixture
def submetida_ce(municipio_ce):
    return DemandFactory(activity=ActivityFactory(municipio=municipio_ce), status="submetida")


def test_fila_do_articulador_nao_inclui_submetida_de_outro_estado(auth_client_articulador_ce, demandas, submetida_ce):
    lista = auth_client_articulador_ce.get(LISTA, {"aguardando_minha_acao": "true"})

    assert _ids(lista) == [submetida_ce.pk]
    assert demandas["sub"].pk not in _ids(lista)
    assert lista.data["count"] == auth_client_articulador_ce.get(CONTAGEM).data["total"]


def test_fila_de_articulador_com_outro_perfil_respeita_o_estado(api_client, demandas, submetida_ce, territory_rn):
    user = UserFactory(
        email="articulador.fgd@test.com",
        profiles=[
            (RoleFactory(slug="articulador-estadual", nome="Articulador Estadual"), territory_rn),
            (RoleFactory(slug="fgd", nome="FGD"), None),
        ],
    )
    api_client.force_authenticate(user)

    lista = api_client.get(LISTA, {"aguardando_minha_acao": "true"})

    assert set(_ids(lista)) == {demandas["sub"].pk, demandas["aut"].pk, demandas["atend"].pk, demandas["outra"].pk}
    assert submetida_ce.pk not in _ids(lista)
    assert lista.data["count"] == api_client.get(CONTAGEM).data["total"]


def test_schema_da_listagem_e_paginado_e_documenta_os_filtros():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    operacao = schema["paths"][LISTA]["get"]

    resposta = operacao["responses"]["200"]["content"]["application/json"]["schema"]
    envelope = schema["components"]["schemas"][resposta["$ref"].rsplit("/", 1)[-1]]
    assert {"count", "next", "previous", "results"} <= set(envelope["properties"])
    parametros = {p["name"]: p for p in operacao["parameters"]}
    assert {
        "limit", "offset", "activity", "atividade", "status", "aguardando_minha_acao", "tipo", "rubrica",
        "solicitante", "acao", "submeta", "meta", "territorio", "periodo_inicio", "periodo_fim",
        "responsavel_etapa_atual",
    } <= set(parametros)
    assert parametros["status"]["schema"]["type"] == "array"
