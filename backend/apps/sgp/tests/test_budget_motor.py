import threading
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase

from apps.core.tests.factories import UserFactory
from apps.sgp.models import BudgetAllocation, BudgetTransaction
from apps.sgp.services import budget as budget_service
from apps.sgp.tests.factories import (
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Tipo = BudgetTransaction.Tipo
Nivel = BudgetAllocation.Nivel


class TestReservar:
    def test_reservar_incrementa_comprometido(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        tx = budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-1", usuario=usuario,
        )

        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("300")
        assert tx.tipo == Tipo.RESERVA
        assert BudgetTransaction.objects.filter(allocation=allocation, tipo=Tipo.RESERVA).count() == 1

    def test_reservar_acima_do_saldo(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("100"))
        usuario = UserFactory()

        with pytest.raises(budget_service.SaldoInsuficienteError) as exc_info:
            budget_service.reservar(
                allocation=allocation, valor=Decimal("150"), demanda_id="demanda-2", usuario=usuario,
            )
        assert "100" in str(exc_info.value)

        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("0")
        assert not BudgetTransaction.objects.filter(allocation=allocation).exists()

    def test_reservar_valor_negativo_rejeitado(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        with pytest.raises(ValueError):
            budget_service.reservar(
                allocation=allocation, valor=Decimal("-50"), demanda_id="demanda-2b", usuario=usuario,
            )

        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("0")

    def test_reservar_valor_exato_do_saldo(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("500"))
        usuario = UserFactory()

        budget_service.reservar(
            allocation=allocation, valor=Decimal("500"), demanda_id="demanda-3", usuario=usuario,
        )

        allocation.refresh_from_db()
        assert allocation.valor_alocado - allocation.valor_comprometido - allocation.valor_executado == Decimal("0")


class TestExecutar:
    def test_executar_move_comprometido_para_executado(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("400"), demanda_id="demanda-4", usuario=usuario,
        )

        tx = budget_service.executar(demanda_id="demanda-4", usuario=usuario)

        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("0")
        assert allocation.valor_executado == Decimal("400")
        assert tx.tipo == Tipo.EXECUCAO
        assert tx.valor == Decimal("400")

    def test_executar_apos_liberar_falha(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-4b", usuario=usuario,
        )
        budget_service.liberar(demanda_id="demanda-4b", usuario=usuario, motivo="cancelada")

        with pytest.raises(budget_service.DemandaInvalidaError):
            budget_service.executar(demanda_id="demanda-4b", usuario=usuario)


class TestLiberar:
    def test_liberar_devolve_ao_solicitante(self, territory_rn, state_rn):
        # estadual (o "pai") nunca deve ser tocado — nem pela reserva, nem
        # pela liberação. Só a territorial (o solicitante) se move.
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        estadual = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )
        territorial = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            territorio=territory_rn, valor_alocado=Decimal("500"),
        )
        usuario = UserFactory()
        budget_service.reservar(
            allocation=territorial, valor=Decimal("200"), demanda_id="demanda-5", usuario=usuario,
        )

        budget_service.liberar(demanda_id="demanda-5", usuario=usuario, motivo="Demanda cancelada.")

        territorial.refresh_from_db()
        estadual.refresh_from_db()
        assert territorial.valor_comprometido == Decimal("0")
        assert estadual.valor_comprometido == Decimal("0")

    def test_liberar_apos_executar_falha(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-5b", usuario=usuario,
        )
        budget_service.executar(demanda_id="demanda-5b", usuario=usuario)

        with pytest.raises(budget_service.DemandaInvalidaError):
            budget_service.liberar(demanda_id="demanda-5b", usuario=usuario, motivo="cancelada")


class TestIdempotencia:
    def test_reservar_e_idempotente(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        tx1 = budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-6", usuario=usuario,
        )
        tx2 = budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-6", usuario=usuario,
        )

        assert tx1.pk == tx2.pk
        assert BudgetTransaction.objects.filter(demanda_id="demanda-6", tipo=Tipo.RESERVA).count() == 1
        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("300")

    def test_executar_e_idempotente(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-7", usuario=usuario,
        )

        tx1 = budget_service.executar(demanda_id="demanda-7", usuario=usuario)
        tx2 = budget_service.executar(demanda_id="demanda-7", usuario=usuario)

        assert tx1.pk == tx2.pk
        allocation.refresh_from_db()
        assert allocation.valor_executado == Decimal("300")

    def test_liberar_e_idempotente(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-8", usuario=usuario,
        )

        tx1 = budget_service.liberar(demanda_id="demanda-8", usuario=usuario, motivo="x")
        tx2 = budget_service.liberar(demanda_id="demanda-8", usuario=usuario, motivo="x")

        assert tx1.pk == tx2.pk
        allocation.refresh_from_db()
        assert allocation.valor_comprometido == Decimal("0")


class TestVerificarSaldosCommand:
    def test_comando_verificar_saldos_detecta_divergencia(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-9", usuario=usuario,
        )

        # corrompe direto no banco, sem passar pelo motor.
        BudgetAllocation.objects.filter(pk=allocation.pk).update(valor_comprometido=Decimal("999"))

        with pytest.raises(CommandError):
            call_command("verificar_saldos")

    def test_comando_verificar_saldos_passa_sem_divergencia(self):
        allocation = BudgetAllocationFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(
            allocation=allocation, valor=Decimal("300"), demanda_id="demanda-10", usuario=usuario,
        )

        call_command("verificar_saldos")  # não levanta


def test_motor_nao_importa_sgd():
    # AST, não busca de substring — um comentário/docstring mencionando
    # "apps.sgd" (como este arquivo tem, documentando essa mesma regra) não
    # pode derrubar o teste; só import real conta.
    import ast

    with open(budget_service.__file__, encoding="utf-8") as f:
        arvore = ast.parse(f.read())

    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith("apps.sgd") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module and node.module.startswith("apps.sgd"))


class TestReservaConcorrente(TransactionTestCase):
    """TransactionTestCase — precisa de conexões reais concorrentes, o
    django_db padrão do pytest embrulha o teste numa transação só."""

    def setUp(self):
        self.usuario = UserFactory()
        self.allocation = BudgetAllocationFactory(valor_alocado=Decimal("100"))

    def test_reserva_concorrente_respeita_saldo(self):
        resultados = []

        def tentar_reservar(demanda_id):
            connection.close()
            try:
                budget_service.reservar(
                    allocation=self.allocation, valor=Decimal("60"),
                    demanda_id=demanda_id, usuario=self.usuario,
                )
                resultados.append("ok")
            except budget_service.SaldoInsuficienteError:
                resultados.append("falhou")

        t1 = threading.Thread(target=tentar_reservar, args=("demanda-concorrente-1",))
        t2 = threading.Thread(target=tentar_reservar, args=("demanda-concorrente-2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(resultados) == ["falhou", "ok"]
        self.allocation.refresh_from_db()
        assert self.allocation.valor_comprometido <= Decimal("100")
