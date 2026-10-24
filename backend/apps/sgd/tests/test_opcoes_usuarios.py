"""`GET /api/v1/sgd/opcoes/usuarios/`: listas dos filtros de usuário do painel."""
import pytest

from apps.core.tests.factories import RoleFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/opcoes/usuarios/"


@pytest.fixture
def adt_ce(territory_ce):
    return UserFactory(email="adt.ce@test.com", nome="ADT CE", profiles=[(RoleFactory(slug="adt-acr"), territory_ce)])


@pytest.fixture
def adt_inativo(territory_rn):
    return UserFactory(
        email="adt.inativo@test.com", nome="ADT Inativo", ativo=False,
        profiles=[(RoleFactory(slug="adt-acr"), territory_rn)],
    )


def _ids(resposta):
    assert resposta.status_code == 200, resposta.data
    return [item["id"] for item in resposta.data]


def test_solicitantes_para_os_perfis_nacionais(
    auth_client_ugp, solicitante_rn, adt_ce, adt_inativo, usuario_articulador_rn,
):
    resposta = auth_client_ugp.get(URL, {"papel": "solicitante"})

    assert _ids(resposta) == [adt_ce.pk, solicitante_rn.pk]
    assert resposta.data[0] == {"id": adt_ce.pk, "nome": "ADT CE"}


def test_articulador_ve_so_os_solicitantes_do_seu_estado(auth_client_articulador_rn, solicitante_rn, adt_ce):
    assert _ids(auth_client_articulador_rn.get(URL, {"papel": "solicitante"})) == [solicitante_rn.pk]


def test_responsaveis_para_os_perfis_nacionais(
    auth_client_fgd, usuario_articulador_rn, usuario_articulador_ce, usuario_ugp, usuario_fgd, solicitante_rn,
):
    ids = _ids(auth_client_fgd.get(URL, {"papel": "responsavel"}))

    assert set(ids) == {usuario_articulador_rn.pk, usuario_articulador_ce.pk, usuario_ugp.pk, usuario_fgd.pk}


def test_articulador_ve_so_os_articuladores_do_seu_estado_e_os_perfis_nacionais(
    auth_client_articulador_rn, usuario_articulador_rn, usuario_articulador_ce, usuario_ugp, usuario_fgd,
):
    ids = _ids(auth_client_articulador_rn.get(URL, {"papel": "responsavel"}))

    assert set(ids) == {usuario_articulador_rn.pk, usuario_ugp.pk, usuario_fgd.pk}


def test_resposta_ordenada_por_nome(auth_client_ugp, solicitante_rn, adt_ce):
    nomes = [item["nome"] for item in auth_client_ugp.get(URL, {"papel": "solicitante"}).data]

    assert nomes == sorted(nomes)


@pytest.mark.parametrize("parametros", [{"papel": "aprovador"}, {}])
def test_papel_invalido_ou_ausente_responde_400(auth_client_ugp, parametros):
    resposta = auth_client_ugp.get(URL, parametros)

    assert resposta.status_code == 400
    assert "papel" in resposta.data


def test_fora_da_gestao_responde_403(auth_client_solicitante):
    assert auth_client_solicitante.get(URL, {"papel": "solicitante"}).status_code == 403
