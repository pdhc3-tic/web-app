"""Fila "Aguardando minha ação": regra por perfil e rota de contagem."""
import pytest

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgd.models.demand import Demand
from apps.sgd.services.approval import demandas_aguardando_acao, status_aguardando_acao
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/aguardando-minha-acao/contagem/"

TODOS_OS_STATUS = [
    "rascunho", "submetida", "devolvida", "pre_autorizada", "autorizada",
    "em_atendimento", "concluida", "recusada", "cancelada",
]


@pytest.fixture
def demandas_rn(activity_rn, solicitante_rn):
    return {
        status: DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status=status)
        for status in TODOS_OS_STATUS
    }


def _aguardando(user):
    return set(demandas_aguardando_acao(user, Demand.objects.all()).values_list("status", flat=True))


def test_articulador_aguarda_so_as_submetidas_do_proprio_estado(
    demandas_rn, usuario_articulador_rn, usuario_articulador_ce,
):
    assert _aguardando(usuario_articulador_rn) == {"submetida"}
    assert not demandas_aguardando_acao(usuario_articulador_ce, Demand.objects.all()).exists()


def test_ugp_aguarda_as_pre_autorizadas_de_qualquer_territorio(
    demandas_rn, usuario_ugp, municipio_ce, solicitante_rn,
):
    DemandFactory(
        activity=ActivityFactory(municipio=municipio_ce), solicitante=solicitante_rn,
        status="pre_autorizada",
    )

    qs = demandas_aguardando_acao(usuario_ugp, Demand.objects.all())

    assert set(qs.values_list("status", flat=True)) == {"pre_autorizada"}
    assert qs.count() == 2


def test_fgd_aguarda_autorizadas_e_em_atendimento(demandas_rn, usuario_fgd):
    assert _aguardando(usuario_fgd) == {"autorizada", "em_atendimento"}


def test_adt_e_super_admin_nao_tem_fila(demandas_rn, solicitante_rn, usuario_super_admin):
    for usuario in (solicitante_rn, usuario_super_admin):
        assert not demandas_aguardando_acao(usuario, Demand.objects.all()).exists()
        assert status_aguardando_acao(usuario) == []


def test_usuario_com_dois_perfis_recebe_a_uniao(demandas_rn):
    ugp = RoleFactory(slug="ugp", nome="UGP")
    fgd = RoleFactory(slug="fgd", nome="FGD")
    usuario = UserFactory(profiles=[(ugp, None), (fgd, None)])

    assert _aguardando(usuario) == {"pre_autorizada", "autorizada", "em_atendimento"}
    assert status_aguardando_acao(usuario) == ["autorizada", "em_atendimento", "pre_autorizada"]


def test_demanda_decidida_sai_da_fila(demandas_rn, usuario_ugp):
    demanda = demandas_rn["pre_autorizada"]
    demanda.status = "autorizada"
    demanda.save(update_fields=["status"])

    assert not demandas_aguardando_acao(usuario_ugp, Demand.objects.all()).exists()


def test_contagem_exige_autenticacao(api_client):
    assert api_client.get(URL).status_code == 401


def test_contagem_do_articulador(demandas_rn, auth_client_articulador_rn):
    response = auth_client_articulador_rn.get(URL)

    assert response.status_code == 200
    assert response.data == {"total": 1, "status": ["submetida"]}


def test_contagem_da_ugp(demandas_rn, auth_client_ugp):
    response = auth_client_ugp.get(URL)

    assert response.data == {"total": 1, "status": ["pre_autorizada"]}


def test_contagem_da_fgd(demandas_rn, auth_client_fgd):
    response = auth_client_fgd.get(URL)

    assert response.data == {"total": 2, "status": ["autorizada", "em_atendimento"]}


def test_contagem_do_solicitante_e_zero(demandas_rn, auth_client_solicitante):
    response = auth_client_solicitante.get(URL)

    assert response.status_code == 200
    assert response.data == {"total": 0, "status": []}
