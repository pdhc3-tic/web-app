import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.services.approval import transition, validar_transicao
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db

TRANSICOES_VALIDAS = [
    ("rascunho", "submetida"),
    ("submetida", "pre_autorizada"),
    ("submetida", "devolvida"),
    ("devolvida", "submetida"),
    ("pre_autorizada", "autorizada"),
    ("pre_autorizada", "recusada"),
    ("autorizada", "em_atendimento"),
    ("em_atendimento", "concluida"),
]


@pytest.mark.parametrize("de,para", TRANSICOES_VALIDAS)
def test_transicao_valida_aceita(de, para):
    demand = DemandFactory(status=de)
    transition(demand, para)
    assert demand.status == para


def test_transicao_fora_da_tabela_rejeitada():
    demand = DemandFactory(status="rascunho")
    with pytest.raises(DRFValidationError):
        validar_transicao(demand, "autorizada")


def test_transicao_a_partir_de_estado_terminal_rejeitada():
    demand = DemandFactory(status="concluida")
    with pytest.raises(DRFValidationError):
        validar_transicao(demand, "submetida")
