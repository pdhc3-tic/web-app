from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgp.models import BudgetAllocation, BudgetRubrica
from apps.sgp.services import budget as budget_service
from apps.sgp.tests.factories import (
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetAllocation.Nivel


def orcamento_url(meta_id):
    return f"/api/v1/sgp/metas/{meta_id}/orcamento/"


def linha_da_rubrica(response, rubrica):
    return next(linha for linha in response.data if linha["rubrica"]["id"] == rubrica.pk)


class TestOrcamentoLeitura:
    def test_orcamento_lista_todas_rubricas(self, auth_client):
        meta = WorkPlanMetaFactory()

        response = auth_client.get(orcamento_url(meta.pk))

        assert response.status_code == 200
        assert BudgetRubrica.objects.filter(ativo=True).count() == 6
        assert len(response.data) == 6
        for linha in response.data:
            assert Decimal(linha["valor_aprovado"]) == Decimal("0")
            assert Decimal(linha["valor_comprometido"]) == Decimal("0")
            assert linha["detalhamento"] == []

    def test_saldo_disponivel_calculado(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("3000"),
            valor_executado=Decimal("2000"),
        )

        response = auth_client_super_admin.get(orcamento_url(meta.pk))

        linha = linha_da_rubrica(response, rubrica)
        assert Decimal(linha["saldo_disponivel"]) == Decimal("5000")

    def test_saldo_disponivel_desconta_valor_ja_distribuido(
        self, auth_client_super_admin, state_rn,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None,
            valor_alocado=Decimal("4000"), valor_comprometido=Decimal("1000"),
        )

        response = auth_client_super_admin.get(orcamento_url(meta.pk))

        linha = linha_da_rubrica(response, rubrica)
        # aprovado 10000 - distribuido 4000 - comprometido/executado do
        # próprio nacional (0) — o comprometido do estado não conta aqui,
        # já está embutido no que foi distribuído.
        assert Decimal(linha["saldo_disponivel"]) == Decimal("6000")

    def test_ugp_ve_todos_os_niveis(
        self, auth_client_super_admin, state_rn, territory_rn,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("10000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("4000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn, valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.get(orcamento_url(meta.pk))

        linha = linha_da_rubrica(response, rubrica)
        # nacional não entra em detalhamento, só em valor_aprovado.
        assert Decimal(linha["valor_aprovado"]) == Decimal("10000")
        niveis = {d["nivel"] for d in linha["detalhamento"]}
        assert niveis == {"estadual", "territorial"}

    def test_articulador_nao_ve_outro_estado(
        self, auth_client_articulador_rn, state_ce,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_ce, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client_articulador_rn.get(orcamento_url(meta.pk))

        linha = linha_da_rubrica(response, rubrica)
        assert linha["detalhamento"] == []

    def test_adt_ve_apenas_seu_territorio(
        self, auth_client_adt_rn, territory_rn, outro_territorio,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            territorio=territory_rn, valor_alocado=Decimal("500"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            territorio=outro_territorio, valor_alocado=Decimal("700"),
        )

        response = auth_client_adt_rn.get(orcamento_url(meta.pk))

        linha = linha_da_rubrica(response, rubrica)
        territorios_vistos = {d["territorio"]["id"] for d in linha["detalhamento"]}
        assert territorios_vistos == {territory_rn.pk}

    def test_sem_perfil_recebe_403(self, auth_client_sem_acesso):
        meta = WorkPlanMetaFactory()

        response = auth_client_sem_acesso.get(orcamento_url(meta.pk))

        assert response.status_code == 403

    def test_numero_de_queries(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubricas = list(BudgetRubrica.objects.filter(ativo=True))
        # cada factory sem override de território cria um Territory novo —
        # não colide com o UniqueConstraint.
        for i in range(20):
            BudgetAllocationFactory(
                meta=meta, rubrica=rubricas[i % len(rubricas)],
                valor_alocado=Decimal("10"),
            )

        with CaptureQueriesContext(connection) as ctx:
            response = auth_client_super_admin.get(orcamento_url(meta.pk))

        assert response.status_code == 200
        # meta + escopo + agregação + detalhamento — fixo, não escala com
        # rubricas nem alocações.
        assert len(ctx.captured_queries) <= 4


def saldo_url(meta_id, rubrica_slug, valor):
    return f"/api/v1/sgp/orcamento/saldo/?meta={meta_id}&rubrica={rubrica_slug}&valor={valor}"


class TestSaldoConsulta:
    def test_saldo_suficiente(self, auth_client):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client.get(saldo_url(meta.pk, rubrica.slug, "500.00"))

        assert response.status_code == 200
        assert response.data["disponivel"] is True
        assert response.data["nivel"] == "nacional"

    def test_saldo_insuficiente(self, auth_client):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )

        response = auth_client.get(saldo_url(meta.pk, rubrica.slug, "1500.00"))

        assert response.status_code == 200
        assert response.data["disponivel"] is False
        assert response.data["motivo_bloqueio"]

    def test_saldo_zerado_bloqueia(self, auth_client):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None,
            valor_alocado=Decimal("1000"), valor_comprometido=Decimal("1000"),
        )

        response = auth_client.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.status_code == 200
        assert response.data["disponivel"] is False
        assert response.data["motivo_bloqueio"] == budget_service.BLOQUEIO_SALDO_ZERO

    # auth_client_* compartilham a mesma instância de APIClient (a fixture
    # api_client é escopo função, sem parametrização) — combinar duas ou mais
    # num teste só faz o último force_authenticate() vencer pras outras
    # também. Por isso um teste por papel, não os três juntos.
    def test_nivel_resolvido_por_perfil_adt(self, auth_client_adt_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()

        response = auth_client_adt_rn.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.data["nivel"] == "territorial"

    def test_nivel_resolvido_por_perfil_articulador(self, auth_client_articulador_rn):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()

        response = auth_client_articulador_rn.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.data["nivel"] == "estadual"

    def test_nivel_resolvido_por_perfil_ugp(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()

        response = auth_client_super_admin.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.data["nivel"] == "nacional"

    def test_rubrica_invalida(self, auth_client):
        meta = WorkPlanMetaFactory()

        response = auth_client.get(saldo_url(meta.pk, "rubrica-inexistente", "10.00"))

        assert response.status_code == 400

    def test_numero_de_queries(self, auth_client, django_assert_num_queries):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
            estado=None, territorio=None, valor_alocado=Decimal("1000"),
        )

        with django_assert_num_queries(2):
            response = auth_client.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.status_code == 200

    def test_rubrica_valida_sem_alocacao(self, auth_client):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()  # sem nenhuma BudgetAllocation

        response = auth_client.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        # esse ramo (rubrica ok, nível resolvido, sem alocação) faz 1 query a
        # mais que o caminho feliz — profile + allocation (miss) + rubrica
        # (pra distinguir de rubrica inválida). Não escolhi otimizar pra 2
        # aqui porque isso empurraria a query extra pro caminho feliz, que é
        # o que o teste ≤2 da issue realmente cobre.
        assert response.status_code == 200
        assert response.data["disponivel"] is False

    def test_perfil_global_nao_resolve_nivel_unico(self, db):
        from apps.core.tests.factories import RoleFactory, UserFactory
        from rest_framework.test import APIClient

        role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
        usuario = UserFactory(
            email="articulador-global@test.com", nome="Articulador Global",
            profiles=[(role, None)],  # territorio=None = perfil global
        )
        client = APIClient()
        client.force_authenticate(user=usuario)
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()

        response = client.get(saldo_url(meta.pk, rubrica.slug, "10.00"))

        assert response.status_code == 403
