import threading
from decimal import Decimal
from time import monotonic

from django.db import connection
from django.test import TransactionTestCase

from apps.core.tests.factories import MunicipalityFactory, RoleFactory, StateFactory, TerritoryFactory, UserFactory
from apps.sgd.services import balance as balance_service
from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory
from apps.sgp.tests.factories import ActivityFactory, BudgetAllocationFactory, BudgetRubricaFactory, WorkPlanAcaoFactory


class TestReservarDuasTravasConcorrente(TransactionTestCase):
    """TransactionTestCase — precisa de conexões reais concorrentes, o
    django_db padrão do pytest embrulha o teste numa transação só (mesmo
    padrão de apps.sgp.tests.test_budget_motor.TestReservaConcorrente)."""

    def setUp(self):
        territory = TerritoryFactory(nome="Território Concorrência SGD", estados=["RN"])
        state = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        municipio = MunicipalityFactory(
            nome="Mossoró Concorrência", state=state, territory=territory, codigo_ibge="2408900",
        )
        role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
        self.solicitante = UserFactory(email="concorrencia.sgd@test.com", profiles=[(role, territory)])
        activity = ActivityFactory(
            municipio=municipio, tecnico_responsavel=self.solicitante, acao=WorkPlanAcaoFactory(),
        )
        rubrica = BudgetRubricaFactory(slug="rubrica-concorrencia-sgd")
        BudgetAllocationFactory(
            meta=activity.acao.meta, rubrica=rubrica, territorio=territory, valor_alocado=Decimal("1000"),
        )
        self.limite = DemandIndividualLimitFactory(
            solicitante=self.solicitante, rubrica=rubrica, valor_limite=Decimal("100"),
        )
        demand = DemandFactory(activity=activity, solicitante=self.solicitante, status="rascunho")
        self.solicitacao_1 = DemandRequestFactory(
            demanda=demand, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json={
                "tipo_material": "banner", "quantidade": 1,
                "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
            },
        )
        self.solicitacao_2 = DemandRequestFactory(
            demanda=demand, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json={
                "tipo_material": "banner", "quantidade": 1,
                "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
            },
        )

    def test_reserva_concorrente_respeita_limite_individual(self):
        resultados = []

        def tentar_reservar(solicitacao):
            connection.close()
            try:
                balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=self.solicitante)
                resultados.append("ok")
            except Exception:
                resultados.append("falhou")

        t1 = threading.Thread(target=tentar_reservar, args=(self.solicitacao_1,))
        t2 = threading.Thread(target=tentar_reservar, args=(self.solicitacao_2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(resultados) == ["falhou", "ok"]
        self.limite.refresh_from_db()
        assert self.limite.valor_comprometido <= Decimal("100")


class TestVerificarDuasTravasPerformance(TransactionTestCase):
    def setUp(self):
        territory = TerritoryFactory(nome="Território Performance SGD", estados=["RN"])
        state = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        municipio = MunicipalityFactory(
            nome="Mossoró Performance", state=state, territory=territory, codigo_ibge="2408901",
        )
        role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
        self.solicitante = UserFactory(email="performance.sgd@test.com", profiles=[(role, territory)])
        activity = ActivityFactory(
            municipio=municipio, tecnico_responsavel=self.solicitante, acao=WorkPlanAcaoFactory(),
        )
        self.meta = activity.acao.meta
        self.rubrica = BudgetRubricaFactory(slug="rubrica-performance-sgd")
        BudgetAllocationFactory(
            meta=self.meta, rubrica=self.rubrica, territorio=territory, valor_alocado=Decimal("1_000_000"),
        )
        DemandIndividualLimitFactory(
            solicitante=self.solicitante, rubrica=self.rubrica, valor_limite=Decimal("1_000_000"),
        )

    def test_verificacao_das_duas_travas_responde_em_menos_de_300ms(self):
        inicio = monotonic()
        check = balance_service.verificar_duas_travas(
            solicitante=self.solicitante, rubrica=self.rubrica, meta=self.meta, valor=Decimal("100"),
        )
        duracao = monotonic() - inicio

        assert check.disponivel is True
        assert duracao < 0.3
