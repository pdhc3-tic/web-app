import threading
from decimal import Decimal
from time import monotonic

from django.db import connection
from django.test import TransactionTestCase

from apps.core.tests.factories import MunicipalityFactory, RoleFactory, StateFactory, TerritoryFactory, UserFactory
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory
from apps.sgp.tests.factories import ActivityFactory, BudgetAllocationFactory, BudgetRubricaFactory, WorkPlanAcaoFactory


class TestReservarDuasTravasConcorrente(TransactionTestCase):
    """TransactionTestCase — precisa de conexões reais concorrentes, o
    django_db padrão do pytest embrulha o teste numa transação só (mesmo
    padrão de apps.sgp.tests.test_budget_motor.TestReservaConcorrente).

    Exercita o caminho completo (`submeter_demanda`, não `reservar_duas_travas`
    direto) — são duas Demands distintas do mesmo solicitante/rubrica, cada
    uma com uma única solicitação, submetidas ao mesmo tempo."""

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

        campos_grafico = {
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
        }
        self.demand_1 = DemandFactory(activity=activity, solicitante=self.solicitante, status="rascunho")
        DemandRequestFactory(
            demanda=self.demand_1, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json=campos_grafico,
        )
        self.demand_2 = DemandFactory(activity=activity, solicitante=self.solicitante, status="rascunho")
        DemandRequestFactory(
            demanda=self.demand_2, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json=campos_grafico,
        )

    def test_submissao_concorrente_de_duas_demandas_respeita_limite_individual(self):
        resultados = []

        def tentar_submeter(demand):
            connection.close()
            try:
                demand_service.submeter_demanda(demand, usuario=self.solicitante)
                resultados.append("ok")
            except Exception:
                resultados.append("falhou")

        t1 = threading.Thread(target=tentar_submeter, args=(self.demand_1,))
        t2 = threading.Thread(target=tentar_submeter, args=(self.demand_2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(resultados) == ["falhou", "ok"]
        self.limite.refresh_from_db()
        assert self.limite.valor_comprometido <= Decimal("100")


class TestSubmissaoConcorrenteEstouraPoolTerritorial(TransactionTestCase):
    """Dois solicitantes distintos, cada um com limite individual de sobra,
    disputando a mesma alocação territorial apertada — o perdedor da corrida
    (`SaldoInsuficienteError` do motor do SGP, dentro do `select_for_update`
    da alocação) precisa virar 400, não vazar como exceção genérica (500)."""

    def setUp(self):
        territory = TerritoryFactory(nome="Território Concorrência Territorial SGD", estados=["RN"])
        state = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        municipio = MunicipalityFactory(
            nome="Mossoró Territorial", state=state, territory=territory, codigo_ibge="2408902",
        )
        role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
        self.solicitante_1 = UserFactory(email="territorial.um@test.com", profiles=[(role, territory)])
        self.solicitante_2 = UserFactory(email="territorial.dois@test.com", profiles=[(role, territory)])
        activity = ActivityFactory(
            municipio=municipio, tecnico_responsavel=self.solicitante_1, acao=WorkPlanAcaoFactory(),
        )
        rubrica = BudgetRubricaFactory(slug="rubrica-territorial-concorrencia-sgd")
        BudgetAllocationFactory(
            meta=activity.acao.meta, rubrica=rubrica, territorio=territory, valor_alocado=Decimal("100"),
        )
        DemandIndividualLimitFactory(solicitante=self.solicitante_1, rubrica=rubrica, valor_limite=Decimal("1000"))
        DemandIndividualLimitFactory(solicitante=self.solicitante_2, rubrica=rubrica, valor_limite=Decimal("1000"))

        campos_grafico = {
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
        }
        self.demand_1 = DemandFactory(activity=activity, solicitante=self.solicitante_1, status="rascunho")
        DemandRequestFactory(
            demanda=self.demand_1, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json=campos_grafico,
        )
        self.demand_2 = DemandFactory(activity=activity, solicitante=self.solicitante_2, status="rascunho")
        DemandRequestFactory(
            demanda=self.demand_2, rubrica=rubrica, tipo="grafico", valor_estimado=Decimal("60"),
            campos_json=campos_grafico,
        )

    def test_perdedor_da_corrida_recebe_400_pela_api_nao_500(self):
        # Via APIView de verdade (não a função de service direto) — o que
        # importa aqui é o código de status HTTP que chega no cliente, não
        # só o tipo da exceção de serviço internamente.
        from rest_framework.test import APIClient

        status_codes = []

        def tentar_submeter(demand, usuario):
            connection.close()
            client = APIClient()
            client.force_authenticate(user=usuario)
            response = client.post(f"/api/v1/sgd/demandas/{demand.pk}/submeter/")
            status_codes.append(response.status_code)

        t1 = threading.Thread(target=tentar_submeter, args=(self.demand_1, self.solicitante_1))
        t2 = threading.Thread(target=tentar_submeter, args=(self.demand_2, self.solicitante_2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(status_codes) == [200, 400]


class TestVerificarDuasTravasPerformance(TransactionTestCase):
    def setUp(self):
        from apps.sgp.models.budget import BudgetTransaction

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
        allocation = BudgetAllocationFactory(
            meta=self.meta, rubrica=self.rubrica, territorio=territory, valor_alocado=Decimal("1_000_000"),
        )
        DemandIndividualLimitFactory(
            solicitante=self.solicitante, rubrica=self.rubrica, valor_limite=Decimal("1_000_000"),
        )

        # Histórico representativo — sem isso a consulta bate numa tabela vazia,
        # o que não reflete a carga real que o índice precisa aguentar em produção.
        BudgetTransaction.objects.bulk_create([
            BudgetTransaction(
                allocation=allocation, tipo=BudgetTransaction.Tipo.RESERVA,
                valor=Decimal("10"), demanda_id=f"perf-{i}",
            )
            for i in range(1_000)
        ])

    def test_verificacao_das_duas_travas_responde_em_menos_de_300ms(self):
        inicio = monotonic()
        check = balance_service.verificar_duas_travas(
            solicitante=self.solicitante, rubrica=self.rubrica, meta=self.meta, valor=Decimal("100"),
        )
        duracao = monotonic() - inicio

        assert check.disponivel is True
        assert duracao < 0.3
