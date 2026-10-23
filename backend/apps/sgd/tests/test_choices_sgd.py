import pytest
from django.db import models

from apps.sgd import constants
from apps.sgd.constants import Urgencia
from apps.sgd.models.demand import STATUS_CHOICES
from apps.sgd.models.demand_document import TIPO_CHOICES as DOCUMENTO_TIPO_CHOICES
from apps.sgd.models.demand_request import TIPO_CHOICES as SOLICITACAO_TIPO_CHOICES
from apps.sgp.views.choices import CHOICES_PUBLICADOS

pytestmark = pytest.mark.django_db

CHOICES_URL = "/api/v1/choices/"


@pytest.mark.parametrize("chave, opcoes", [
    ("urgencia", Urgencia.choices),
    ("solicitacao_tipo", SOLICITACAO_TIPO_CHOICES),
    ("demanda_status", STATUS_CHOICES),
    ("demanda_documento_tipo", DOCUMENTO_TIPO_CHOICES),
])
def test_choices_do_sgd_publicados_com_valor_e_rotulo(auth_client_solicitante, chave, opcoes):
    response = auth_client_solicitante.get(CHOICES_URL)

    assert response.status_code == 200
    assert response.data[chave] == [{"value": valor, "label": rotulo} for valor, rotulo in opcoes]


def test_urgencia_publicada_no_formato_do_contrato(auth_client_solicitante):
    response = auth_client_solicitante.get(CHOICES_URL)

    assert response.data["urgencia"] == [
        {"value": "normal", "label": "Normal"},
        {"value": "urgente", "label": "Urgente"},
        {"value": "emergencial", "label": "Emergencial"},
    ]


def test_chaves_dos_selects_do_formulario_seguem_os_campos_de_campos_json(auth_client_solicitante):
    response = auth_client_solicitante.get(CHOICES_URL)

    assert {
        "beneficiario_vinculo", "meio_transporte", "classe", "urgencia",
        "tipo_veiculo", "tipo_material", "tipo_refeicao",
    } <= set(response.data)


def test_todo_textchoices_do_sgd_esta_publicado():
    """TextChoices novo em `apps/sgd/constants.py` que não entre no endpoint
    derruba este teste."""
    publicadas = list(CHOICES_PUBLICADOS.values())
    classes = {
        nome: valor for nome, valor in vars(constants).items()
        if isinstance(valor, type) and issubclass(valor, models.TextChoices) and valor is not models.TextChoices
    }
    assert classes
    ausentes = [nome for nome, classe in classes.items() if classe.choices not in publicadas]
    assert not ausentes, f"TextChoices fora do endpoint /choices/: {ausentes}"


def test_listas_dos_modelos_do_sgd_estao_publicadas():
    publicadas = [id(opcoes) for opcoes in CHOICES_PUBLICADOS.values()]
    for opcoes in (STATUS_CHOICES, DOCUMENTO_TIPO_CHOICES, SOLICITACAO_TIPO_CHOICES):
        assert id(opcoes) in publicadas
