import threading
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test import TransactionTestCase

from apps.core.tests.factories import StateFactory, UserFactory
from apps.sgp.models import BudgetAllocation, BudgetTransaction
from apps.sgp.services import budget as budget_service
from apps.sgp.tests.factories import BudgetAllocationFactory, BudgetRubricaFactory, WorkPlanMetaFactory

pytestmark = pytest.mark.django_db

Nivel = BudgetAllocation.Nivel
Tipo = BudgetTransaction.Tipo

REMANEJAR_URL = "/api/v1/sgp/orcamento/remanejamentos/"


def transacoes_url(pk):
    return f"/api/v1/sgp/orcamento/alocacoes/{pk}/transacoes/"


def duas_alocacoes_mesma_meta_rubrica(*, valor_origem=Decimal("1000"), valor_destino=Decimal("500")):
    meta = WorkPlanMetaFactory()
    rubrica = BudgetRubricaFactory()
    estado_a = StateFactory(sigla="RN", nome="Rio Grande do Norte")
    estado_b = StateFactory(sigla="CE", nome="Ceará")
    origem = BudgetAllocationFactory(
        meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
        estado=estado_a, territorio=None, valor_alocado=valor_origem,
    )
    destino = BudgetAllocationFactory(
        meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
        estado=estado_b, territorio=None, valor_alocado=valor_destino,
    )
    return origem, destino


class TestRemanejamentoValido:
    def test_remanejamento_valido(self, auth_client_super_admin):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "300.00", "justificativa": "Demanda emergencial na CE.",
            },
            format="json",
        )

        assert response.status_code == 201
        origem.refresh_from_db()
        destino.refresh_from_db()
        assert origem.valor_alocado == Decimal("700.00")
        assert destino.valor_alocado == Decimal("800.00")
        assert len(response.data) == 2
        assert {t["tipo"] for t in response.data} == {"remanejamento"}
        debito, credito = response.data
        assert debito["justificativa"] == credito["justificativa"] == "Demanda emergencial na CE."
        assert debito["criado_por"] == credito["criado_por"]
        assert Decimal(debito["valor"]) == Decimal("-300.00")
        assert Decimal(credito["valor"]) == Decimal("300.00")

    def test_remanejamento_entre_niveis_diferentes(self, auth_client_super_admin, state_rn, territory_rn):
        # o cenário que motiva a feature (§5.3.3): UGP cobre um território
        # sem saldo usando o saldo do próprio estado — não é estadual↔estadual.
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        estadual = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("500"),
        )
        territorial = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            territorio=territory_rn, valor_alocado=Decimal("100"),
            valor_comprometido=Decimal("100"),  # saldo territorial zerado
        )

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": estadual.pk, "destino_allocation": territorial.pk,
                "valor": "50.00", "justificativa": "Território sem saldo, estado cobre.",
            },
            format="json",
        )

        assert response.status_code == 201
        estadual.refresh_from_db()
        territorial.refresh_from_db()
        assert estadual.valor_alocado == Decimal("450.00")
        assert territorial.valor_alocado == Decimal("150.00")

    def test_exige_justificativa(self, auth_client_super_admin):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {"origem_allocation": origem.pk, "destino_allocation": destino.pk, "valor": "100.00"},
            format="json",
        )

        assert response.status_code == 400
        assert "justificativa" in response.data

    def test_justificativa_vazia_rejeitada(self, auth_client_super_admin):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "100.00", "justificativa": "   ",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "justificativa" in response.data


class TestPermissoes:
    # auth_client_* compartilham a mesma instância de APIClient (fixture
    # api_client é escopo função, sem parametrização) — dois na mesma
    # assinatura faz o último force_authenticate() valer pros dois. Por isso
    # dois testes, não um com as duas chamadas.
    def test_articulador_403(self, auth_client_articulador_rn):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()
        payload = {
            "origem_allocation": origem.pk, "destino_allocation": destino.pk,
            "valor": "100.00", "justificativa": "x",
        }

        response = auth_client_articulador_rn.post(REMANEJAR_URL, payload, format="json")

        assert response.status_code == 403

    def test_adt_403(self, auth_client_adt_rn):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()
        payload = {
            "origem_allocation": origem.pk, "destino_allocation": destino.pk,
            "valor": "100.00", "justificativa": "x",
        }

        response = auth_client_adt_rn.post(REMANEJAR_URL, payload, format="json")

        assert response.status_code == 403

    def test_ugp_no_super_admin_executa(self, auth_client):
        # auth_client é perfil "ugp" puro, não "super-admin" — o critério
        # nomeia os dois papéis, não só o mais permissivo.
        origem, destino = duas_alocacoes_mesma_meta_rubrica()

        response = auth_client.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "100.00", "justificativa": "x",
            },
            format="json",
        )

        assert response.status_code == 201


class TestValidacaoDeCombinacao:
    def test_rubricas_diferentes_rejeitado(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        estado_a = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        estado_b = StateFactory(sigla="CE", nome="Ceará")
        origem = BudgetAllocationFactory(
            meta=meta, nivel=Nivel.ESTADUAL, estado=estado_a, territorio=None, valor_alocado=Decimal("1000"),
        )
        destino = BudgetAllocationFactory(
            meta=meta, nivel=Nivel.ESTADUAL, estado=estado_b, territorio=None, valor_alocado=Decimal("500"),
        )  # rubrica diferente (default da factory: nova a cada chamada)

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "100.00", "justificativa": "x",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_metas_diferentes_rejeitado(self, auth_client_super_admin):
        rubrica = BudgetRubricaFactory()
        estado_a = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        estado_b = StateFactory(sigla="CE", nome="Ceará")
        origem = BudgetAllocationFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=estado_a, territorio=None, valor_alocado=Decimal("1000"),
        )
        destino = BudgetAllocationFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=estado_b, territorio=None, valor_alocado=Decimal("500"),
        )  # meta diferente (default da factory: nova a cada chamada)

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "100.00", "justificativa": "x",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_acima_do_saldo_da_origem(self, auth_client_super_admin):
        origem, destino = duas_alocacoes_mesma_meta_rubrica(valor_origem=Decimal("100"))

        response = auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "150.00", "justificativa": "x",
            },
            format="json",
        )

        assert response.status_code == 400
        origem.refresh_from_db()
        destino.refresh_from_db()
        assert origem.valor_alocado == Decimal("100")
        assert destino.valor_alocado == Decimal("500")


class TestAtomicidade:
    def test_atomicidade(self):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()
        usuario = UserFactory()

        original_create = BudgetTransaction.objects.create
        chamadas = {"n": 0}

        def create_que_falha_na_segunda(*args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise RuntimeError("falha forçada no crédito")
            return original_create(*args, **kwargs)

        with patch.object(BudgetTransaction.objects, "create", side_effect=create_que_falha_na_segunda):
            with pytest.raises(RuntimeError):
                budget_service.remanejar(
                    origem=origem, destino=destino, valor=Decimal("100"),
                    usuario=usuario, justificativa="teste de atomicidade",
                )

        origem.refresh_from_db()
        destino.refresh_from_db()
        assert origem.valor_alocado == Decimal("1000")
        assert destino.valor_alocado == Decimal("500")
        assert not BudgetTransaction.objects.filter(allocation__in=[origem, destino]).exists()


class TestHistoricoDeTransacoes:
    def test_historico_respeita_escopo_territorial(self, auth_client_articulador_rn):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()  # origem=RN, destino=CE

        resposta_no_escopo = auth_client_articulador_rn.get(transacoes_url(origem.pk))
        resposta_fora_do_escopo = auth_client_articulador_rn.get(transacoes_url(destino.pk))

        assert resposta_no_escopo.status_code == 200
        assert resposta_fora_do_escopo.status_code == 403

    def test_historico_de_transacoes(self, auth_client_super_admin):
        origem, destino = duas_alocacoes_mesma_meta_rubrica()

        auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "100.00", "justificativa": "primeiro remanejamento",
            },
            format="json",
        )
        auth_client_super_admin.post(
            REMANEJAR_URL,
            {
                "origem_allocation": origem.pk, "destino_allocation": destino.pk,
                "valor": "50.00", "justificativa": "segundo remanejamento",
            },
            format="json",
        )

        response = auth_client_super_admin.get(transacoes_url(origem.pk))

        assert response.status_code == 200
        valores = [Decimal(t["valor"]) for t in response.data]
        assert len(valores) == 2
        # ordem cronológica decrescente — a mais recente (segunda) primeiro.
        datas = [t["criado_em"] for t in response.data]
        assert datas == sorted(datas, reverse=True)


class TestConcorrenciaRemanejamento(TransactionTestCase):
    """Duas threads remanejando em direções opostas (A→B e B→A) travando as
    mesmas duas linhas em ordem potencialmente invertida — sem lock por pk
    crescente em `remanejar`, isso é candidato a deadlock do Postgres."""

    def setUp(self):
        self.usuario = UserFactory()
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        estado_a = StateFactory(sigla="RN", nome="Rio Grande do Norte")
        estado_b = StateFactory(sigla="CE", nome="Ceará")
        self.allocation_a = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=estado_a, territorio=None, valor_alocado=Decimal("1000"),
        )
        self.allocation_b = BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=estado_b, territorio=None, valor_alocado=Decimal("1000"),
        )

    def test_direcoes_opostas_nao_geram_deadlock(self):
        erros = []

        def remanejar(origem, destino):
            connection.close()
            try:
                budget_service.remanejar(
                    origem=origem, destino=destino, valor=Decimal("50"),
                    usuario=self.usuario, justificativa="concorrência",
                )
            except Exception as exc:
                erros.append(exc)

        t1 = threading.Thread(target=remanejar, args=(self.allocation_a, self.allocation_b))
        t2 = threading.Thread(target=remanejar, args=(self.allocation_b, self.allocation_a))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert erros == []
        self.allocation_a.refresh_from_db()
        self.allocation_b.refresh_from_db()
        assert self.allocation_a.valor_alocado == Decimal("1000")
        assert self.allocation_b.valor_alocado == Decimal("1000")
