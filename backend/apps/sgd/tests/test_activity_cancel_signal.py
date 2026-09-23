from unittest.mock import patch

import pytest

from apps.core.models.notifications import Notification
from apps.sgd.services import balance as balance_service
from apps.sgd.tasks import cancelar_demandas_da_atividade
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def test_activity_cancelada_agenda_task_de_cancelamento(django_capture_on_commit_callbacks, activity_rn):
    """O signal só agenda a task (via transaction.on_commit) — quem cancela
    de fato é apps.sgd.tasks.cancelar_demandas_da_atividade, rodando fora da
    transação da request (ver o motivo no próprio signal)."""
    with patch("apps.sgd.tasks.cancelar_demandas_da_atividade.delay") as mocked_delay:
        with django_capture_on_commit_callbacks(execute=True):
            activity_rn.status = "cancelada"
            activity_rn.justificativa = "Cancelada por decisão da equipe."
            activity_rn.save(update_fields=["status", "justificativa"])

    mocked_delay.assert_called_once_with(activity_rn.pk)


def test_task_cancela_demandas_nao_atendidas_e_libera_saldo(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada por decisão da equipe."
    activity_rn.save(update_fields=["status", "justificativa"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "cancelada"

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == 0
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == 0

    assert Notification.objects.filter(
        evento="demand_cancelada_automatico", user=demand.solicitante,
    ).exists()
    assert Notification.objects.filter(
        evento="demand_cancelada_automatico", user=usuario_articulador_rn,
    ).exists()


def test_task_nao_afeta_demanda_ja_concluida(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="concluida")

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada."
    activity_rn.save(update_fields=["status", "justificativa"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "concluida"


def test_task_ignora_activity_que_mudou_de_status_de_novo(activity_rn, demand_request_rn):
    """Entre o commit que agendou a task e ela rodar, a Activity pode ter
    voltado pra outro status (ex.: reativada) — a task não deve cancelar
    nada nesse caso."""
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    activity_rn.status = "planejado"
    activity_rn.save(update_fields=["status"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "submetida"
