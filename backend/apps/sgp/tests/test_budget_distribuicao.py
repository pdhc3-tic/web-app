import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.test import TransactionTestCase

from apps.core.tests.factories import StateFactory, TerritoryFactory
from apps.sgp.models import BudgetAllocation, BudgetTransaction
from apps.sgp.tests.factories import (
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetAllocation.Nivel


def alocacoes_url(meta_id):
    return f"/api/v1/sgp/metas/{meta_id}/orcamento/alocacoes/"


def alocacao_detail_url(pk):
    return f"/api/v1/sgp/orcamento/alocacoes/{pk}/"


class TestDistribuicaoEstadual:
    def test_distribuicao_dentro_do_teto(self, auth_client_super_admin, state_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "5000.00",
            },
            format="json",
        )

        assert response.status_code == 201
        assert Decimal(response.data["valor_alocado"]) == Decimal("5000.00")

    def test_distribuicao_acima_do_teto_nacional(self, auth_client_super_admin, state_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "15000.00",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "10000" in str(response.data)

    def test_soma_de_estados_nao_excede_meta(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("9000"),
        )
        estados = [
            StateFactory(sigla=sigla, nome=nome)
            for sigla, nome in [("RN", "Rio Grande do Norte"), ("CE", "Ceará"), ("PB", "Paraíba")]
        ]

        for estado in estados:
            response = auth_client_super_admin.post(
                alocacoes_url(meta.pk),
                {
                    "rubrica_id": rubrica.pk, "nivel": "estadual",
                    "estado_id": estado.pk, "valor_alocado": "3000.00",
                },
                format="json",
            )
            assert response.status_code == 201

        quarto_estado = StateFactory(sigla="PE", nome="Pernambuco")
        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": quarto_estado.pk, "valor_alocado": "0.01",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_territorial_limitado_ao_saldo_estadual(self, auth_client_super_admin, state_rn, territory_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_rn.pk, "valor_alocado": "1500.00",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_reserva_ugp_nao_aceita_filhas(self, auth_client_super_admin, state_rn):
        """"Reserva própria da UGP" = a própria linha nacional, já 100%
        distribuída — tentar alocar mais é o teto normal estourando."""
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )
        outro_estado = StateFactory(sigla="CE", nome="Ceará")

        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": outro_estado.pk, "valor_alocado": "0.01",
            },
            format="json",
        )

        assert response.status_code == 400


class TestReducaoDeAlocacao:
    def test_reducao_abaixo_do_comprometido(self, auth_client_super_admin, state_rn):
        allocation = BudgetAllocationFactory(
            nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("5000"),
        )

        response = auth_client_super_admin.patch(
            alocacao_detail_url(allocation.pk),
            {"valor_alocado": "3000.00"},
            format="json",
        )

        assert response.status_code == 400


class TestPermissoes:
    def test_articulador_outro_estado_403(
        self, auth_client_articulador_rn, state_ce, territory_ce,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_ce, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_articulador_rn.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_ce.pk, "valor_alocado": "100.00",
            },
            format="json",
        )

        assert response.status_code == 403

    def test_adt_nao_aloca(self, auth_client_adt_rn, territory_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()

        response = auth_client_adt_rn.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_rn.pk, "valor_alocado": "100.00",
            },
            format="json",
        )

        assert response.status_code == 403


class TestTrilhaDeAuditoria:
    def test_gera_transaction_de_remanejamento(self, auth_client_super_admin, state_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            alocacoes_url(meta.pk),
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "1000.00",
            },
            format="json",
        )

        assert response.status_code == 201
        transacoes = BudgetTransaction.objects.filter(allocation_id=response.data["id"])
        assert transacoes.count() == 1
        transacao = transacoes.get()
        assert transacao.tipo == BudgetTransaction.Tipo.REMANEJAMENTO
        assert transacao.criado_por_id is not None


class TestConcorrencia(TransactionTestCase):
    """TransactionTestCase (não pytest fixture) porque precisa de duas
    conexões reais concorrentes — o django_db padrão do pytest embrulha o
    teste numa transação só, que threads separadas não conseguem furar."""

    def setUp(self):
        from apps.core.tests.factories import RoleFactory, StateFactory, UserFactory
        from apps.sgp.tests.factories import BudgetRubricaFactory as _RubricaFactory
        from apps.sgp.tests.factories import WorkPlanMetaFactory as _MetaFactory

        self.role_super_admin = RoleFactory(slug="super-admin", nome="Super Admin")
        self.usuario = UserFactory(
            email="concorrencia@test.com", nome="Concorrência",
            profiles=[(self.role_super_admin, None)],
        )
        self.meta = _MetaFactory()
        self.rubrica = _RubricaFactory()
        self.estado = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        BudgetAllocationFactory(
            meta=self.meta, rubrica=self.rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )

    def test_concorrencia_nao_estoura_teto(self):
        from rest_framework.test import APIClient

        resultados = []

        def distribuir(sigla, nome):
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.usuario)
            estado = StateFactory(sigla=sigla, nome=nome)
            response = client.post(
                alocacoes_url(self.meta.pk),
                {
                    "rubrica_id": self.rubrica.pk, "nivel": "estadual",
                    "estado_id": estado.pk, "valor_alocado": "600.00",
                },
                format="json",
            )
            resultados.append(response.status_code)

        t1 = threading.Thread(target=distribuir, args=("CE", "Ceará"))
        t2 = threading.Thread(target=distribuir, args=("PB", "Paraíba"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(resultados) == [201, 400]
        total_alocado = sum(
            BudgetAllocation.objects.filter(
                meta=self.meta, rubrica=self.rubrica, nivel=Nivel.ESTADUAL,
            ).values_list("valor_alocado", flat=True),
            Decimal("0"),
        )
        assert total_alocado <= Decimal("1000")
