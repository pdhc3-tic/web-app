import re
import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.core.tests.factories import StateFactory, TerritoryFactory, UserFactory
from apps.sgp.budget import services as budget_service
from apps.sgp.models import BudgetPool, BudgetTransaction
from apps.sgp.tests.factories import (
    BudgetPoolFactory,
    BudgetRubricaFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel


POOLS_URL = "/api/v1/sgp/orcamento/pools/"


def pool_url(pk):
    return f"{POOLS_URL}{pk}/"


def alias_de_criacao_url(meta_id):
    return f"/api/v1/sgp/metas/{meta_id}/orcamento/alocacoes/"


def alias_de_detalhe_url(pk):
    return f"/api/v1/sgp/orcamento/alocacoes/{pk}/"


class TestDistribuicaoEstadual:
    def test_distribuicao_dentro_do_teto(self, auth_client_super_admin, state_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "5000.00",
            },
            format="json",
        )

        assert response.status_code == 201
        assert Decimal(response.data["valor_alocado"]) == Decimal("5000.00")

    def test_distribuicao_acima_do_teto_nacional(self, auth_client_super_admin, state_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "15000.00",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "10000" in str(response.data)

    def test_soma_de_estados_nao_excede_o_nacional(self, auth_client_super_admin):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("9000"),
        )
        estados = [
            StateFactory(sigla=sigla, nome=nome)
            for sigla, nome in [("RN", "Rio Grande do Norte"), ("CE", "Ceará"), ("PB", "Paraíba")]
        ]

        for estado in estados:
            response = auth_client_super_admin.post(
                POOLS_URL,
                {
                    "rubrica_id": rubrica.pk, "nivel": "estadual",
                    "estado_id": estado.pk, "valor_alocado": "3000.00",
                },
                format="json",
            )
            assert response.status_code == 201

        quarto_estado = StateFactory(sigla="PE", nome="Pernambuco")
        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": quarto_estado.pk, "valor_alocado": "0.01",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_territorial_limitado_ao_saldo_estadual(self, auth_client_super_admin, state_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_rn.pk, "valor_alocado": "1500.00",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_reserva_ugp_nao_aceita_filhas(self, auth_client_super_admin, state_rn):
        """Uma reserva nacional bloqueia filhas mesmo quando ainda tem saldo."""
        rubrica = BudgetRubricaFactory()
        reserva = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "nacional",
                "valor_alocado": "1000.00", "reserva_ugp": True,
            },
            format="json",
        )
        assert reserva.status_code == 201
        assert reserva.data["reserva_ugp"] is True

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "0.01",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "não pode receber alocações-filhas" in str(response.data)

    def test_reserva_ugp_so_pode_ser_nacional(self, auth_client_super_admin, state_rn):
        rubrica = BudgetRubricaFactory()

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "100.00",
                "reserva_ugp": True,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "só é aplicável ao nível nacional" in str(response.data)


class TestCriacaoDePool:
    def test_territorial_nao_grava_o_estado_informado(self, auth_client_super_admin, state_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial", "estado_id": state_rn.pk,
                "territorio_id": territory_rn.pk, "valor_alocado": "100.00",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["estado"] is None

    def test_pool_repetido_e_400(self, auth_client_super_admin):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {"rubrica_id": rubrica.pk, "nivel": "nacional", "valor_alocado": "500.00"},
            format="json",
        )

        assert response.status_code == 400
        assert "Já existe um pool" in str(response.data)


class TestAliasDasRotasDeAlocacao:
    def test_criacao_pela_rota_da_meta_vira_pool_sem_meta(self, auth_client_super_admin):
        rubrica = BudgetRubricaFactory()

        response = auth_client_super_admin.post(
            alias_de_criacao_url(WorkPlanMetaFactory().pk),
            {"rubrica_id": rubrica.pk, "nivel": "nacional", "valor_alocado": "500.00"},
            format="json",
        )

        assert response.status_code == 201
        assert BudgetPool.objects.filter(pk=response.data["id"], rubrica=rubrica).exists()

    def test_criacao_com_meta_inexistente_e_404(self, auth_client_super_admin):
        response = auth_client_super_admin.post(
            alias_de_criacao_url(999999),
            {"rubrica_id": BudgetRubricaFactory().pk, "nivel": "nacional", "valor_alocado": "500.00"},
            format="json",
        )

        assert response.status_code == 404

    def test_alteracao_e_transacoes_pelo_id_do_pool(self, auth_client_super_admin):
        pool = BudgetPoolFactory(
            nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=Decimal("500"),
        )

        alteracao = auth_client_super_admin.patch(
            alias_de_detalhe_url(pool.pk), {"valor_alocado": "700.00"}, format="json",
        )
        transacoes = auth_client_super_admin.get(f"{alias_de_detalhe_url(pool.pk)}transacoes/")

        assert alteracao.status_code == 200
        assert Decimal(alteracao.data["valor_alocado"]) == Decimal("700.00")
        assert transacoes.status_code == 200
        assert transacoes.data[0]["pool"] == pool.pk
        assert transacoes.data[0]["allocation"] == pool.pk


class TestReducaoDePool:
    def test_reducao_abaixo_do_comprometido(self, auth_client_super_admin, state_rn):
        pool = BudgetPoolFactory(
            nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("5000"),
        )

        response = auth_client_super_admin.patch(
            pool_url(pool.pk),
            {"valor_alocado": "3000.00"},
            format="json",
        )

        assert response.status_code == 400


class TestOrdemDeLock:
    def test_ajuste_trava_o_pool_e_o_pai_em_ordem_de_pk(self, state_rn, territory_rn):
        """Como `remanejar`: o estadual, criado antes, é travado antes do territorial
        ajustado, e não depois dele."""
        rubrica = BudgetRubricaFactory()
        estadual = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None,
            valor_alocado=Decimal("1000"),
        )
        territorial = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("100"),
        )

        with CaptureQueriesContext(connection) as consultas:
            budget_service.atualizar_valor_alocado(territorial, novo_valor=Decimal("200"), usuario=UserFactory())

        travadas = [
            int(achado.group(1))
            for consulta in consultas if "FOR UPDATE" in consulta["sql"]
            for achado in [re.search(r'"sgp_budgetpool"\."id" = (\d+)', consulta["sql"])] if achado
        ]
        assert travadas[:2] == [estadual.pk, territorial.pk]


class TestPermissoes:
    def test_articulador_outro_estado_403(
        self, auth_client_articulador_rn, state_ce, territory_ce,
    ):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_ce, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_articulador_rn.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_ce.pk, "valor_alocado": "100.00",
            },
            format="json",
        )

        assert response.status_code == 403

    def test_adt_nao_aloca(self, auth_client_adt_rn, territory_rn):
        rubrica = BudgetRubricaFactory()

        response = auth_client_adt_rn.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "territorial",
                "territorio_id": territory_rn.pk, "valor_alocado": "100.00",
            },
            format="json",
        )

        assert response.status_code == 403


class TestTrilhaDeAuditoria:
    def test_gera_transaction_de_remanejamento(self, auth_client_super_admin, state_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )

        response = auth_client_super_admin.post(
            POOLS_URL,
            {
                "rubrica_id": rubrica.pk, "nivel": "estadual",
                "estado_id": state_rn.pk, "valor_alocado": "1000.00",
            },
            format="json",
        )

        assert response.status_code == 201
        transacoes = BudgetTransaction.objects.filter(pool_id=response.data["id"])
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

        self.role_super_admin = RoleFactory(slug="super-admin", nome="Super Admin")
        self.usuario = UserFactory(
            email="concorrencia@test.com", nome="Concorrência",
            profiles=[(self.role_super_admin, None)],
        )
        self.rubrica = _RubricaFactory()
        self.estado = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        BudgetPoolFactory(
            rubrica=self.rubrica, nivel=Nivel.NACIONAL,
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
                POOLS_URL,
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
            BudgetPool.objects.filter(
                rubrica=self.rubrica, nivel=Nivel.ESTADUAL,
            ).values_list("valor_alocado", flat=True),
            Decimal("0"),
        )
        assert total_alocado <= Decimal("1000")
