import pytest

from apps.core.models.notifications import Notification
from apps.sgd.services import balance as balance_service

pytestmark = pytest.mark.django_db


def test_activity_adiada_mantem_demanda_e_saldo_e_notifica(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    nova_data = activity_rn.data_inicio
    activity_rn.status = "adiada"
    activity_rn.save(update_fields=["status"])

    demand.refresh_from_db()
    assert demand.status == "submetida"

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == demand_request_rn.valor_estimado

    assert Notification.objects.filter(
        evento="demand_atividade_adiada", user=usuario_articulador_rn,
    ).exists()


def test_activity_adiada_nao_renotifica_em_saves_subsequentes(
    activity_rn, demand_request_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    activity_rn.status = "adiada"
    activity_rn.save(update_fields=["status"])
    Notification.objects.filter(evento="demand_atividade_adiada").delete()

    activity_rn.descricao_narrativa = "Detalhe atualizado."
    activity_rn.save(update_fields=["descricao_narrativa"])

    assert not Notification.objects.filter(evento="demand_atividade_adiada").exists()
