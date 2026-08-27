import sys
import types
from types import SimpleNamespace

import pytest
from django.utils import timezone


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
