"""`manage.py verificar_saldos` confere também o limite individual do SGD."""
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sgd.models import DemandIndividualLimit, DemandRequest
from apps.sgd.services import balance as balance_service
from apps.sgd.services.reconciliacao import divergencias_dos_limites

pytestmark = pytest.mark.django_db


def test_passa_com_o_saldo_movido_pelos_servicos(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=Decimal("800"), usuario=solicitante_rn,
    )

    assert divergencias_dos_limites() == []
    call_command("verificar_saldos")


def test_falha_com_comprometido_diferente_das_reservas_ativas(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("999"))

    assert divergencias_dos_limites() == [
        f"Limite individual #{limite_individual_rn.pk}: valor_comprometido=999.00 "
        "mas as reservas ativas somam 1000.00"
    ]
    with pytest.raises(CommandError, match=f"Limite individual #{limite_individual_rn.pk}"):
        call_command("verificar_saldos")


def test_reserva_executada_nao_conta_no_comprometido(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.executar_duas_travas(
        demand_request=demand_request_rn, valor_pago=Decimal("900"), usuario=solicitante_rn,
    )

    assert divergencias_dos_limites() == []


def test_falha_com_reserva_ativa_sem_limite(demand_request_rn):
    DemandRequest.objects.filter(pk=demand_request_rn.pk).update(valor_reservado=Decimal("1000"))

    assert divergencias_dos_limites() == [
        f"Solicitação #{demand_request_rn.pk}: reserva ativa de 1000.00 sem limite individual "
        "do solicitante na rubrica"
    ]
