import sys
import types
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.core.tests.factories import RoleFactory, UserFactory


URL = "/api/v1/sgp/formularios-disponiveis/"


class FakeQuerySet(list):
    created = []

    def __init__(self, forms, filters=None):
        super().__init__(forms)
        self.filters = filters or {}
        self.q = None
        type(self).created.append(self)

    def filter(self, *args, **kwargs):
        queryset = FakeQuerySet(list(self), {**self.filters, **kwargs})
        if args:
            queryset.q = args[0]
        return queryset

    def order_by(self, *args):
        return self


class FakeObjects:
    def __init__(self, forms):
        self.forms = forms

    def filter(self, **kwargs):
        return FakeQuerySet(list(self.forms), kwargs)


def install_fake_sgf(monkeypatch, forms):
    module = types.ModuleType("apps.sgf.models")
    module.FormularioSGF = type("FormularioSGF", (), {"objects": FakeObjects(forms)})
    monkeypatch.setitem(sys.modules, "apps.sgf.models", module)


@pytest.fixture(autouse=True)
def clear_fake_querysets():
    FakeQuerySet.created = []
    yield
    FakeQuerySet.created = []


@pytest.mark.django_db
def test_available_forms_returns_only_published_upf_contract(auth_client, territory, monkeypatch):
    form = SimpleNamespace(
        pk=1,
        nome="Diagnóstico produtivo",
        versao="1.0",
        descricao="Levantamento inicial",
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert response.data[0]["id"] == 1
    assert response.data[0]["nome"] == "Diagnóstico produtivo"
    assert response.data[0]["versao"] == "1.0"
    assert response.data[0]["descricao"] == "Levantamento inicial"
    assert set(response.data[0]) == {
        "id", "nome", "versao", "descricao", "atualizado_em"
    }
    assert FakeQuerySet.created[0].filters == {
        "status": "publicado",
        "tipo_entidade_alvo": "upf",
    }
    assert FakeQuerySet.created[-1].q is not None
    assert ("territorio__isnull", True) in FakeQuerySet.created[-1].q.children


@pytest.mark.django_db
def test_available_forms_without_sgf_returns_empty_list(auth_client):
    response = auth_client.get(URL)

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_nenhum_formulario_disponivel_com_territorio_valido_retorna_lista_vazia(
    auth_client, territory, monkeypatch
):
    install_fake_sgf(monkeypatch, [])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_usuario_sem_territorio_retorna_lista_vazia_sem_consultar_sgf(
    api_client, monkeypatch
):
    form = SimpleNamespace(
        pk=99,
        nome="Formulário Fantasma",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])
    usuario = UserFactory(email="sem-territorio@example.com", nome="Sem Território")
    api_client.force_authenticate(user=usuario)

    response = api_client.get(URL)

    assert response.status_code == 200
    assert response.data == []
    # Curto-circuito por território: nem chega a consultar o FormularioSGF,
    # apesar de o fake ter sido instalado com um formulário disponível.
    assert FakeQuerySet.created == []


@pytest.mark.django_db
def test_requisicao_sem_autenticacao_retorna_401(api_client):
    response = api_client.get(URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_usuario_com_acesso_revogado_retorna_401(api_client):
    role = RoleFactory(slug="ugp", nome="UGP")
    usuario = UserFactory(
        email="revogado@example.com", nome="Revogado", profiles=[(role, None)]
    )
    usuario.acesso_revogado = True
    usuario.save(update_fields=["acesso_revogado"])
    api_client.force_authenticate(user=usuario)

    response = api_client.get(URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_usuario_com_role_nao_sgp_ainda_ve_formularios_disponiveis(
    auth_client_fgd, territory, monkeypatch
):
    form = SimpleNamespace(
        pk=6,
        nome="Formulário Visível a Qualquer Role",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client_fgd.get(URL)

    assert response.status_code == 200
    assert response.data[0]["id"] == 6


@pytest.mark.django_db
def test_usuario_com_multiplos_territorios_aplica_filtro_correto(
    api_client, territory_rn, territory_ce, monkeypatch
):
    role = RoleFactory(slug="adt-acr", nome="ADT")
    usuario = UserFactory(
        email="multi-territorio@example.com",
        nome="ADT Multi",
        profiles=[(role, territory_rn), (role, territory_ce)],
    )
    api_client.force_authenticate(user=usuario)
    form = SimpleNamespace(
        pk=7,
        nome="Formulário Multi Território",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = api_client.get(URL)

    assert response.status_code == 200
    entries = dict(FakeQuerySet.created[-1].q.children)
    territorios_no_filtro = set(entries["territorio__in"].values_list("pk", flat=True))
    assert territorios_no_filtro == {territory_rn.pk, territory_ce.pk}


@pytest.mark.django_db
def test_filtro_exclui_formularios_nao_publicados_por_status(
    auth_client, territory, monkeypatch
):
    form = SimpleNamespace(
        pk=2,
        nome="Formulário Rascunho",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert FakeQuerySet.created[0].filters["status"] == "publicado"


@pytest.mark.django_db
def test_filtro_aplica_tipo_entidade_alvo_igual_upf(
    auth_client, territory, monkeypatch
):
    form = SimpleNamespace(
        pk=3,
        nome="Formulário SCA",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert FakeQuerySet.created[0].filters["tipo_entidade_alvo"] == "upf"


@pytest.mark.django_db
def test_filtro_de_territorio_usa_territorios_do_usuario_autenticado(
    auth_client_adt_rn, territory_rn, monkeypatch
):
    form = SimpleNamespace(
        pk=4,
        nome="Formulário RN",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client_adt_rn.get(URL)

    assert response.status_code == 200
    assert FakeQuerySet.created[-1].q is not None
    entries = dict(FakeQuerySet.created[-1].q.children)
    assert list(entries["territorio__in"].values_list("pk", flat=True)) == [
        territory_rn.pk
    ]


@pytest.mark.django_db
def test_ordenacao_por_atualizado_em_preservada_com_multiplos_formularios(
    auth_client, territory, monkeypatch
):
    mais_antigo = SimpleNamespace(
        pk=10,
        nome="Formulário Antigo",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now() - timedelta(days=2),
    )
    mais_recente = SimpleNamespace(
        pk=11,
        nome="Formulário Recente",
        versao="1.0",
        descricao=None,
        atualizado_em=timezone.now(),
    )
    install_fake_sgf(monkeypatch, [mais_antigo, mais_recente])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [10, 11]


@pytest.mark.django_db
def test_serializer_nao_expoe_campos_internos_status_tipo_entidade_territorio(
    auth_client, territory, monkeypatch
):
    form = SimpleNamespace(
        pk=5,
        nome="Formulário Completo",
        versao="1.0",
        descricao="Descrição",
        atualizado_em=timezone.now(),
        status="publicado",
        tipo_entidade_alvo="upf",
        territorio=None,
    )
    install_fake_sgf(monkeypatch, [form])

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert set(response.data[0]) == {
        "id", "nome", "versao", "descricao", "atualizado_em"
    }


@pytest.mark.django_db
def test_excecao_na_consulta_retorna_lista_vazia_com_http_200(
    auth_client, territory, monkeypatch
):
    class RaisingObjects:
        def filter(self, **kwargs):
            raise RuntimeError("falha simulada de consulta")

    module = types.ModuleType("apps.sgf.models")
    module.FormularioSGF = type("FormularioSGF", (), {"objects": RaisingObjects()})
    monkeypatch.setitem(sys.modules, "apps.sgf.models", module)

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert response.data == []
