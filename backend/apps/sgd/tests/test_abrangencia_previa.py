"""Prévia da abrangência para quem vai criar a demanda, Articuladores responsáveis e UF
da atividade no contexto."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/abrangencia/"


def _articulador(nome, territorio):
    return UserFactory(nome=nome, profiles=[(RoleFactory(slug="articulador-estadual"), territorio)])


@pytest.fixture
def activity_ce(db, municipio_ce):
    return ActivityFactory(municipio=municipio_ce, status="planejado")


# ---------- Prévia ----------

def test_previa_do_adt_traz_estado_territorio_e_articulador(
    auth_client_solicitante, territory_rn, usuario_articulador_rn, usuario_articulador_ce,
):
    resp = auth_client_solicitante.get(URL)

    assert resp.status_code == 200, resp.data
    assert resp.data == {
        "estado_sigla": "RN",
        "territorio": {"id": territory_rn.pk, "nome": "Território RN"},
        "articuladores": [{"id": usuario_articulador_rn.pk, "nome": "Articulador RN"}],
        "atividade_fora_do_territorio": False,
    }


def test_atividade_de_outro_estado_sai_fora_do_territorio(auth_client_solicitante, activity_ce, activity_rn):
    fora = auth_client_solicitante.get(URL, {"activity_id": activity_ce.pk})
    dentro = auth_client_solicitante.get(URL, {"activity_id": activity_rn.pk})

    assert fora.data["atividade_fora_do_territorio"] is True
    assert fora.data["estado_sigla"] == "RN"
    assert dentro.data["atividade_fora_do_territorio"] is False


def test_estado_sem_articulador_devolve_lista_vazia(auth_client_solicitante, usuario_articulador_ce):
    resp = auth_client_solicitante.get(URL)

    assert resp.data["articuladores"] == []


def test_varios_articuladores_vem_ordenados_por_nome(auth_client_solicitante, territory_rn):
    zeca = _articulador("Zeca", territory_rn)
    ana = _articulador("Ana", territory_rn)
    inativo = _articulador("Bia", territory_rn)
    inativo.ativo = False
    inativo.save(update_fields=["ativo"])

    resp = auth_client_solicitante.get(URL)

    assert resp.data["articuladores"] == [{"id": ana.pk, "nome": "Ana"}, {"id": zeca.pk, "nome": "Zeca"}]


def test_super_admin_cria_no_nivel_nacional(auth_client_super_admin, activity_ce, usuario_articulador_ce):
    resp = auth_client_super_admin.get(URL, {"activity_id": activity_ce.pk})

    assert resp.data == {
        "estado_sigla": None, "territorio": None, "articuladores": [], "atividade_fora_do_territorio": False,
    }


def test_atividade_inexistente_e_404(auth_client_solicitante):
    assert auth_client_solicitante.get(URL, {"activity_id": 999_999}).status_code == 404


@pytest.mark.parametrize("activity_id", ["abc", "²", "0", "-1", "1.5"])
def test_activity_id_que_nao_e_id_valido_e_400(auth_client_solicitante, activity_id):
    resp = auth_client_solicitante.get(URL, {"activity_id": activity_id})

    assert resp.status_code == 400
    assert "activity_id" in resp.data


@pytest.mark.parametrize("cliente", ["auth_client_articulador_rn", "auth_client_ugp", "auth_client_fgd"])
def test_quem_nao_cria_demanda_recebe_403(request, cliente):
    assert request.getfixturevalue(cliente).get(URL).status_code == 403


def test_usuario_sem_perfil_recebe_403(api_client):
    api_client.force_authenticate(user=UserFactory())

    assert api_client.get(URL).status_code == 403


def test_previa_bate_com_o_que_a_criacao_grava(auth_client_solicitante, activity_ce, usuario_articulador_rn):
    previa = auth_client_solicitante.get(URL, {"activity_id": activity_ce.pk}).data

    criada = auth_client_solicitante.post(
        "/api/v1/sgd/demandas/", {"titulo": "Visita", "activity_id": activity_ce.pk}, format="json",
    )

    assert criada.status_code == 201, criada.data
    assert criada.data["estado_sigla"] == previa["estado_sigla"]
    assert criada.data["territorio"] == previa["territorio"]["id"]
    assert criada.data["articuladores"] == previa["articuladores"]
    assert criada.data["atividade_fora_do_territorio"] == previa["atividade_fora_do_territorio"]


# ---------- Leitura da demanda ----------

def test_demanda_traz_articuladores_e_uf_da_atividade(
    auth_client_solicitante, solicitante_rn, activity_ce, usuario_articulador_rn,
):
    demand = DemandFactory(activity=activity_ce, solicitante=solicitante_rn, estado_sigla="RN", territorio=None)

    resp = auth_client_solicitante.get(f"/api/v1/sgd/demandas/{demand.pk}/")

    assert resp.data["articuladores"] == [{"id": usuario_articulador_rn.pk, "nome": "Articulador RN"}]
    assert resp.data["contexto"]["municipio_estado_sigla"] == "CE"


def test_demanda_nacional_nao_tem_articulador(auth_client_super_admin, usuario_super_admin, activity_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=usuario_super_admin, estado_sigla="", territorio=None)

    resp = auth_client_super_admin.get(f"/api/v1/sgd/demandas/{demand.pk}/")

    assert resp.data["articuladores"] == []


def test_listagem_consulta_os_articuladores_uma_vez_por_estado(
    auth_client_ugp, activity_rn, usuario_articulador_rn,
):
    def consultas_da_listagem():
        with CaptureQueriesContext(connection) as consultas:
            resp = auth_client_ugp.get("/api/v1/sgd/demandas/")
        assert resp.status_code == 200
        return len(consultas)

    DemandFactory(activity=activity_rn)
    # A primeira requisição do usuário pode carregar dados que ficam em cache.
    consultas_da_listagem()
    uma = consultas_da_listagem()
    for _ in range(4):
        DemandFactory(activity=activity_rn)
    cinco = consultas_da_listagem()

    assert cinco == uma
