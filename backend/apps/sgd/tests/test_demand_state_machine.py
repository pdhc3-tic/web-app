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


def test_aplicar_transicao_persiste_status_e_data_da_mudanca():
    from datetime import timedelta

    from django.utils import timezone

    from apps.sgd.models.demand import Demand
    from apps.sgd.services.approval import aplicar_transicao

    demand = DemandFactory(status="rascunho")
    antiga = timezone.now() - timedelta(days=10)
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=antiga)
    demand.refresh_from_db()

    aplicar_transicao(demand, "submetida")

    demand.refresh_from_db()
    assert demand.status == "submetida"
    assert demand.status_alterado_em > antiga


def test_marcar_cancelada_dispensa_tabela_de_transicoes():
    from datetime import timedelta

    from django.utils import timezone

    from apps.sgd.models.demand import Demand
    from apps.sgd.services.approval import marcar_cancelada

    demand = DemandFactory(status="pre_autorizada")
    antiga = timezone.now() - timedelta(days=10)
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=antiga)
    demand.refresh_from_db()

    marcar_cancelada(demand)

    demand.refresh_from_db()
    assert demand.status == "cancelada"
    assert demand.status_alterado_em > antiga
