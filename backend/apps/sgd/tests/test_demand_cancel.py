from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service

pytestmark = pytest.mark.django_db


def test_cancelar_rascunho_nunca_reservado_nao_altera_saldo(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    """Um Rascunho nunca chegou a reservar — cancelar não pode mexer no
    comprometido de ninguém."""
    demand = demand_request_rn.demanda
    assert demand.status == "rascunho"

    demand_service.cancelar_demanda(demand, usuario=solicitante_rn)

    demand.refresh_from_db()
    assert demand.status == "cancelada"
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_cancelar_submetida_libera_reserva(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado

    demand_service.cancelar_demanda(demand, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_cancelar_pre_autorizada_libera_reserva(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])

    demand_service.cancelar_demanda(demand, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_cancelar_apos_autorizada_bloqueado(demand_request_rn, solicitante_rn):
    demand = demand_request_rn.demanda
    demand.status = "autorizada"
    demand.save(update_fields=["status"])

    with pytest.raises(DRFValidationError):
        demand_service.cancelar_demanda(demand, usuario=solicitante_rn)


def test_cancelar_duas_vezes_nao_libera_duas_vezes(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    """Chamar `liberar_duas_travas` de novo numa reserva já liberada (ex.: o
    signal de atividade cancelada rodando sobre uma demanda que o próprio
    solicitante acabou de cancelar) não pode decrementar `valor_comprometido`
    além de zero."""
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)

    balance_service.liberar_duas_travas(
        demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Primeira liberação.",
    )
    balance_service.liberar_duas_travas(
        demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Segunda liberação (não deveria fazer nada).",
    )

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
