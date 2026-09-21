from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.sgd.models.demand import Demand
from apps.sgd.tasks import check_demand_inactivity_alert
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def _voltar_no_tempo_dias_uteis(demand, dias_uteis: int) -> None:
    """Aproxima dias corridos suficientes pra cobrir `dias_uteis` úteis —
    não precisa ser exato porque os testes usam 4 e 5, bem afastados de um
    fim de semana no meio (ver `_dias_uteis_entre`)."""
    referencia = timezone.now() - timedelta(days=dias_uteis + 2)
    Demand.objects.filter(pk=demand.pk).update(atualizado_em=referencia)


def test_demanda_sem_movimentacao_ha_5_dias_uteis_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")
    _voltar_no_tempo_dias_uteis(demand, 7)  # >= 5 dias úteis com folga

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 1
    notificar.assert_called_once()


def test_demanda_com_4_dias_nao_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")
    Demand.objects.filter(pk=demand.pk).update(atualizado_em=timezone.now() - timedelta(days=4))

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 0
    notificar.assert_not_called()


def test_demanda_terminal_nunca_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="concluida")
    _voltar_no_tempo_dias_uteis(demand, 30)

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        check_demand_inactivity_alert()

    notificar.assert_not_called()
