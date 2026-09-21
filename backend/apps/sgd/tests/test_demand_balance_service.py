from decimal import Decimal

import pytest

from apps.sgd.services import balance as balance_service
from apps.sgd.tests.factories import DemandIndividualLimitFactory, DemandRequestFactory

pytestmark = pytest.mark.django_db


def test_bloqueio_trava_individual_sem_limite_configurado(solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn):
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, meta=activity_rn.acao.meta, valor=Decimal("100"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "individual"


def test_bloqueio_trava_individual_insuficiente(solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn, limite_individual_rn):
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, meta=activity_rn.acao.meta,
        valor=Decimal("999999"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "individual"


def test_bloqueio_trava_territorial_esgotada(solicitante_rn, rubrica_diarias, activity_rn, limite_individual_rn):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=100, valor_comprometido=100,
    )
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, meta=activity_rn.acao.meta, valor=Decimal("50"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "territorial"


def test_reservar_duas_travas_reserva_nos_dois_lados(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == demand_request_rn.valor_estimado


def test_reservar_duas_travas_idempotente(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado


def test_ajustar_duas_travas_valor_menor_libera_diferenca(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = demand_request_rn.valor_estimado - Decimal("300")

    balance_service.ajustar_duas_travas(demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == novo_valor
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == novo_valor


def test_liberar_duas_travas_libera_100_por_cento(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Recusada.")

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_executar_duas_travas_valor_pago_menor_libera_diferenca(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.valor_autorizado = demand_request_rn.valor_estimado
    demand_request_rn.save(update_fields=["valor_autorizado"])

    valor_pago = demand_request_rn.valor_estimado - Decimal("200")
    balance_service.executar_duas_travas(demand_request=demand_request_rn, valor_pago=valor_pago, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert limite_individual_rn.valor_executado == valor_pago

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_executado == valor_pago


def test_autorizar_excedente_exige_justificativa(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    from apps.core.tests.factories import StateFactory
    from apps.sgp.models.budget import BudgetAllocation
    from apps.sgp.tests.factories import BudgetAllocationFactory
    from rest_framework.exceptions import ValidationError as DRFValidationError

    origem = BudgetAllocationFactory(
        meta=demand_request_rn.demanda.activity.acao.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.ESTADUAL, territorio=None,
        estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"), valor_alocado=5000,
    )
    with pytest.raises(DRFValidationError):
        balance_service.autorizar_excedente(
            demand_request=demand_request_rn, origem_allocation=origem,
            valor_excedente=Decimal("500"), justificativa="", usuario=solicitante_rn,
        )
