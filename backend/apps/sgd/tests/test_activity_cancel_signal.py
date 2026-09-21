import pytest

from apps.core.models.notifications import Notification
from apps.sgd.services import balance as balance_service
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def test_activity_cancelada_cancela_demandas_nao_atendidas_e_libera_saldo(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada por decisão da equipe."
    activity_rn.save(update_fields=["status", "justificativa"])

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


def test_activity_cancelada_nao_afeta_demanda_ja_concluida(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="concluida")

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada."
    activity_rn.save(update_fields=["status", "justificativa"])

    demand.refresh_from_db()
    assert demand.status == "concluida"
