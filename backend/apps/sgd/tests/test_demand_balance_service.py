from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
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


def test_ajustar_duas_travas_acima_do_limite_bloqueia_sem_bypass(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = limite_individual_rn.valor_limite + Decimal("1")

    with pytest.raises(DRFValidationError):
        balance_service.ajustar_duas_travas(demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn)


def test_ajustar_duas_travas_com_bypass_autoriza_excedente_sem_elevar_limite(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    """RF16: `ignorar_limite_individual=True` autoriza o ajuste pontual acima do
    saldo individual disponível, mas `valor_limite` continua o mesmo."""
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    valor_limite_antes = limite_individual_rn.valor_limite
    novo_valor = valor_limite_antes + Decimal("1")

    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn,
        ignorar_limite_individual=True,
    )

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == novo_valor
    assert limite_individual_rn.valor_limite == valor_limite_antes


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

    origem = BudgetAllocationFactory(
        meta=demand_request_rn.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.ESTADUAL, territorio=None,
        estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"), valor_alocado=5000,
    )
    with pytest.raises(DRFValidationError):
        balance_service.autorizar_excedente(
            demand_request=demand_request_rn, origem_allocation=origem,
            valor_excedente=Decimal("500"), justificativa="", usuario=solicitante_rn,
        )


def test_autorizar_excedente_com_justificativa_remaneja_sem_elevar_limite_individual(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """RF16: o remanejamento emergencial move o pool territorial, mas nunca eleva
    `valor_limite` — senão o solicitante ganharia teto maior permanentemente por
    causa de um excedente pontual."""
    from apps.core.tests.factories import StateFactory
    from apps.sgp.models.budget import BudgetAllocation, BudgetTransaction
    from apps.sgp.tests.factories import BudgetAllocationFactory

    origem = BudgetAllocationFactory(
        meta=demand_request_rn.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.ESTADUAL, territorio=None,
        estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"), valor_alocado=Decimal("5000"),
    )
    valor_limite_antes = limite_individual_rn.valor_limite

    balance_service.autorizar_excedente(
        demand_request=demand_request_rn, origem_allocation=origem,
        valor_excedente=Decimal("500"), justificativa="Demanda urgente aprovada pela UGP.",
        usuario=solicitante_rn,
    )

    origem.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    limite_individual_rn.refresh_from_db()

    assert origem.valor_alocado == Decimal("4500")
    assert allocation_territorial_rn.valor_alocado == Decimal("10500")
    assert limite_individual_rn.valor_limite == valor_limite_antes
    assert BudgetTransaction.objects.filter(
        allocation=origem, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
    ).exists()


def test_submeter_demanda_bloqueio_de_uma_solicitacao_identifica_so_a_bloqueada(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """§4.1: verificação é rubrica a rubrica — a solicitação sem bloqueio não
    deve aparecer na lista de bloqueios, mesmo a submissão inteira falhando
    (tudo-ou-nada, RF13: nada é reservado até todas passarem)."""
    from apps.sgp.tests.factories import BudgetRubricaFactory

    demand = demand_request_rn.demanda
    rubrica_sem_limite = BudgetRubricaFactory(slug="rubrica-sem-limite-sgd")
    solicitacao_bloqueada = DemandRequestFactory(
        demanda=demand, rubrica=rubrica_sem_limite, tipo="grafico", valor_estimado=Decimal("100"),
        campos_json={
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
        },
    )

    with pytest.raises(DRFValidationError) as excinfo:
        demand_service.submeter_demanda(demand, usuario=solicitante_rn)

    bloqueios = excinfo.value.detail["solicitacoes_bloqueadas"]
    assert str(solicitacao_bloqueada.pk) in bloqueios
    assert str(demand_request_rn.pk) not in bloqueios

    demand.refresh_from_db()
    assert demand.status == "rascunho"
    assert demand.solicitacoes.count() == 2
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
