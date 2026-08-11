"""
Testes do endpoint GET /api/v1/sca/sync/forms/.

Fail-safe: mesmo sem formulários SGF disponíveis, retorna lista vazia 200.
Quando o SGF existe, os formulários são restritos ao escopo territorial do
técnico autenticado (formulários do território + globais).
"""

import sys
import types
from types import SimpleNamespace

import pytest
from django.db.models import Q
from django.utils import timezone

from apps.core.tests.factories import UserFactory


def get_forms(auth_client, since=None):
    params = {}
    if since is not None:
        params["since"] = since.isoformat()
    return auth_client.get("/api/v1/sca/sync/forms/", data=params, format="json")


# ---------------------------------------------------------------------------
# Fake minimal do app SGF (FormularioSGF ainda não existe no repo).
# Captura os filtros aplicados pelo serviço para validar o escopo territorial.
# ---------------------------------------------------------------------------


class _FakeQS(list):
    created = []

    def __init__(self, forms, filters=None):
        super().__init__(forms)
        self.filters = filters or {}
        self.q = None
        type(self).created.append(self)

    def filter(self, *args, **kwargs):
        qs = _FakeQS(list(self), {**self.filters, **kwargs})
        if args:
            qs.q = args[0]
        return qs

    def order_by(self, *args):
        return self


class _FakeObjects:
    def __init__(self, forms):
        self._forms = forms

    def filter(self, **kwargs):
        return _FakeQS(list(self._forms), dict(kwargs))


def _install_fake_sgf(monkeypatch, forms):
    fake_module = types.ModuleType("apps.sgf.models")
    fake_module.FormularioSGF = type(
        "FormularioSGF", (), {"objects": _FakeObjects(forms)}
    )
    monkeypatch.setitem(sys.modules, "apps.sgf.models", fake_module)
    return fake_module


@pytest.fixture
def form_publicado():
    return SimpleNamespace(
        pk=1,
        nome="Formulário A",
        versao="1.0",
        tipo_entidade_alvo="upf",
        schema_json={},
        atualizado_em=timezone.now(),
    )


@pytest.fixture(autouse=True)
def _limpa_registry():
    _FakeQS.created = []
    yield
    _FakeQS.created = []


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_forms_sem_sgf_disponivel_retorna_200_lista_vazia(auth_client):
    response = get_forms(auth_client)

    assert response.status_code == 200
    assert response.data["formularios"] == []
    assert response.data["server_time"]


@pytest.mark.django_db
def test_forms_filtra_por_territorios_do_tecnico(auth_client, usuario, territory, monkeypatch, form_publicado):
    _install_fake_sgf(monkeypatch, [form_publicado])

    response = get_forms(auth_client)

    assert response.status_code == 200
    assert [f["id"] for f in response.data["formularios"]] == [1]

    final = _FakeQS.created[-1]
    expected = Q(territorio_id__in={territory.pk}) | Q(territorio_id__isnull=True)
    assert final.q == expected


@pytest.mark.django_db
def test_forms_usuario_sem_territorios_retorna_vazio(auth_client, monkeypatch, form_publicado):
    sem_perfil = UserFactory(email="sem-perfil@test.com", nome="Sem Perfil")
    auth_client.force_authenticate(user=sem_perfil)
    _install_fake_sgf(monkeypatch, [form_publicado])

    response = get_forms(auth_client)

    assert response.status_code == 200
    assert response.data["formularios"] == []
