import pytest

from apps.sgd import constants
from apps.sgd.constants import URGENCIA_CHOICES
from apps.sgd.models.demand import STATUS_CHOICES
from apps.sgd.models.demand_document import TIPO_CHOICES as DOCUMENTO_TIPO_CHOICES
from apps.sgd.models.demand_request import TIPO_CHOICES as SOLICITACAO_TIPO_CHOICES
from apps.sgp.views.choices import CHOICES_PUBLICADOS

pytestmark = pytest.mark.django_db

CHOICES_URL = "/api/v1/choices/"


@pytest.mark.parametrize("chave, opcoes", [
    ("urgencia", URGENCIA_CHOICES),
    ("solicitacao_tipo", SOLICITACAO_TIPO_CHOICES),
    ("demanda_status", STATUS_CHOICES),
    ("demanda_documento_tipo", DOCUMENTO_TIPO_CHOICES),
])
def test_choices_do_sgd_publicados_com_valor_e_rotulo(auth_client_solicitante, chave, opcoes):
    response = auth_client_solicitante.get(CHOICES_URL)

    assert response.status_code == 200
    assert response.data[chave] == [{"value": valor, "label": rotulo} for valor, rotulo in opcoes]


def test_chaves_dos_selects_do_formulario_seguem_os_campos_de_campos_json(auth_client_solicitante):
    response = auth_client_solicitante.get(CHOICES_URL)

    assert {
        "beneficiario_vinculo", "meio_transporte", "classe", "urgencia",
        "tipo_veiculo", "tipo_material", "tipo_refeicao",
    } <= set(response.data)


def test_toda_constante_de_choices_do_sgd_esta_publicada():
    """Constante de choices nova em `apps/sgd/constants.py` que não entre no
    endpoint derruba este teste."""
    publicadas = [id(opcoes) for opcoes in CHOICES_PUBLICADOS.values()]
    constantes = {nome: valor for nome, valor in vars(constants).items() if nome.endswith("_CHOICES")}
    assert constantes
    ausentes = [nome for nome, valor in constantes.items() if id(valor) not in publicadas]
    assert not ausentes, f"Constantes fora do endpoint /choices/: {ausentes}"


def test_listas_dos_modelos_do_sgd_estao_publicadas():
    publicadas = [id(opcoes) for opcoes in CHOICES_PUBLICADOS.values()]
    for opcoes in (STATUS_CHOICES, DOCUMENTO_TIPO_CHOICES, SOLICITACAO_TIPO_CHOICES):
        assert id(opcoes) in publicadas
