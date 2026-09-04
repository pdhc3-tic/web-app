import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.sgp.models import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgp.tests.factories import (
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    BudgetTransactionFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

RUBRICAS_ESPERADAS = {
    "diarias", "passagens-aereas", "locacao-veiculo",
    "alimentacao-refeicoes", "material-grafico", "equipamentos-capital",
}


class TestSeedRubricas:
    def test_seed_cria_seis_rubricas(self):
        assert BudgetRubrica.objects.count() == 6
        assert set(BudgetRubrica.objects.values_list("slug", flat=True)) == RUBRICAS_ESPERADAS

    def test_seed_e_idempotente(self):
        antes = set(BudgetRubrica.objects.values_list("slug", "ordem"))

        # nome de módulo começa com dígito — mesma técnica do MigrationLoader do Django.
        migration = importlib.import_module("apps.sgp.migrations.0017_seed_rubricas")
        migration.seed_rubricas(django_apps, None)

        assert BudgetRubrica.objects.count() == 6
        assert set(BudgetRubrica.objects.values_list("slug", "ordem")) == antes


class TestAllocationConstraints:
    def test_allocation_unica_por_combinacao(self, territory_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica,
            nivel=BudgetAllocation.Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BudgetAllocationFactory(
                    meta=meta, rubrica=rubrica,
                    nivel=BudgetAllocation.Nivel.TERRITORIAL,
                    estado=None, territorio=territory_rn,
                )

    def test_allocation_nacional_unica_mesmo_com_estado_e_territorio_nulos(self):
        # nacional tem estado e território NULL nos dois lados — sem
        # nulls_distinct=False no UniqueConstraint, o Postgres deixaria passar.
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica,
            nivel=BudgetAllocation.Nivel.NACIONAL,
            estado=None, territorio=None,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BudgetAllocationFactory(
                    meta=meta, rubrica=rubrica,
                    nivel=BudgetAllocation.Nivel.NACIONAL,
                    estado=None, territorio=None,
                )

    def test_nivel_nacional_rejeita_estado(self, state_rn):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BudgetAllocationFactory(
                    nivel=BudgetAllocation.Nivel.NACIONAL,
                    estado=state_rn, territorio=None,
                )

    def test_nivel_estadual_exige_estado(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BudgetAllocationFactory(
                    nivel=BudgetAllocation.Nivel.ESTADUAL,
                    estado=None, territorio=None,
                )

    def test_nivel_territorial_exige_territorio(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BudgetAllocationFactory(
                    nivel=BudgetAllocation.Nivel.TERRITORIAL,
                    estado=None, territorio=None,
                )


class TestTransactionImutavel:
    def test_transaction_e_imutavel(self):
        transacao = BudgetTransactionFactory()
        transacao.valor = Decimal("999.00")

        with pytest.raises(ValueError):
            transacao.save()

    def test_transaction_nao_pode_ser_deletada(self):
        transacao = BudgetTransactionFactory()

        with pytest.raises(ProtectedError):
            transacao.delete()


class TestValoresDecimal:
    def test_valores_sao_decimal(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("0.01"))
        allocation.refresh_from_db()

        assert type(allocation.valor_alocado) is Decimal
        assert allocation.valor_alocado == Decimal("0.01")

    def test_valores_comprometido_e_executado_sao_decimal(self):
        allocation = BudgetAllocationFactory(
            valor_comprometido=Decimal("0.01"), valor_executado=Decimal("0.01"),
        )
        allocation.refresh_from_db()

        assert type(allocation.valor_comprometido) is Decimal
        assert type(allocation.valor_executado) is Decimal

    def test_transaction_valor_e_decimal(self):
        transacao = BudgetTransactionFactory(valor=Decimal("0.01"))
        transacao.refresh_from_db()

        assert type(transacao.valor) is Decimal
        assert transacao.valor == Decimal("0.01")
