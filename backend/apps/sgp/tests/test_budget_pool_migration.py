"""Migration que agrega as alocações em pools por rubrica e nível, sem a Meta."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

ANTES = [("sgp", "0008_preencher_escopo_das_transferencias")]
DEPOIS = [("sgp", "0011_remover_budgetallocation")]

pytestmark = pytest.mark.django_db(transaction=True)


def _migrar(alvo):
    executor = MigrationExecutor(connection)
    executor.migrate(alvo)
    return MigrationExecutor(connection).loader.project_state(alvo).apps


@pytest.fixture
def banco_antes_da_migracao():
    yield _migrar(ANTES)
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _alocacoes(apps):
    Meta = apps.get_model("sgp", "WorkPlanMeta")
    Rubrica = apps.get_model("sgp", "BudgetRubrica")
    Estado = apps.get_model("core", "State")
    Territorio = apps.get_model("core", "Territory")
    Alocacao = apps.get_model("sgp", "BudgetAllocation")

    inicio, fim = date(2026, 1, 1), date(2026, 12, 31)
    meta_1 = Meta.objects.create(numero=91, titulo="Meta 91", data_inicio=inicio, data_fim=fim)
    meta_2 = Meta.objects.create(numero=92, titulo="Meta 92", data_inicio=inicio, data_fim=fim)
    rubrica = Rubrica.objects.create(nome="Rubrica da migração", slug="rubrica-da-migracao")
    estado, _ = Estado.objects.get_or_create(sigla="ZZ", defaults={"nome": "Estado da migração"})
    territorio = Territorio.objects.create(nome="Território da migração", estados=["ZZ"])

    def nacional(meta, alocado, **campos):
        return Alocacao.objects.create(meta=meta, rubrica=rubrica, nivel="nacional", valor_alocado=alocado, **campos)

    return {
        "rubrica": rubrica,
        "estado": estado,
        "territorio": territorio,
        "nacional_1": nacional(meta_1, Decimal("1000"), reserva_ugp=True),
        "nacional_2": nacional(meta_2, Decimal("500")),
        "estadual_1": Alocacao.objects.create(
            meta=meta_1, rubrica=rubrica, nivel="estadual", estado=estado, valor_alocado=Decimal("300"),
        ),
        "territorial_1": Alocacao.objects.create(
            meta=meta_1, rubrica=rubrica, nivel="territorial", territorio=territorio, estado=estado,
            valor_alocado=Decimal("100"), valor_comprometido=Decimal("40"),
        ),
        "territorial_2": Alocacao.objects.create(
            meta=meta_2, rubrica=rubrica, nivel="territorial", territorio=territorio,
            valor_alocado=Decimal("50"), valor_executado=Decimal("10"),
        ),
    }


def test_agrega_por_rubrica_e_nivel_sem_a_meta(banco_antes_da_migracao):
    dados = _alocacoes(banco_antes_da_migracao)

    apps = _migrar(DEPOIS)

    Pool = apps.get_model("sgp", "BudgetPool")
    pools = Pool.objects.filter(rubrica_id=dados["rubrica"].pk)
    assert pools.count() == 3
    nacional = pools.get(nivel="nacional")
    assert nacional.valor_alocado == Decimal("1500")
    # Só uma das duas linhas era reserva: agregada a uma linha comum, deixa de ser.
    assert nacional.reserva_ugp is False
    territorial = pools.get(nivel="territorial")
    assert territorial.valor_alocado == Decimal("150")
    assert territorial.valor_comprometido == Decimal("40")
    assert territorial.valor_executado == Decimal("10")
    # O estado informado em só uma das linhas não pode separar o mesmo território.
    assert territorial.estado_id is None
    assert pools.get(nivel="estadual").estado_id == dados["estado"].pk


def test_reaponta_transacoes_e_remanejamentos(banco_antes_da_migracao):
    dados = _alocacoes(banco_antes_da_migracao)
    apps_antes = banco_antes_da_migracao
    Transacao = apps_antes.get_model("sgp", "BudgetTransaction")
    Transferencia = apps_antes.get_model("sgp", "BudgetTransfer")
    transacao_1 = Transacao.objects.create(allocation=dados["nacional_1"], tipo="remanejamento", valor=Decimal("1"))
    transacao_2 = Transacao.objects.create(allocation=dados["nacional_2"], tipo="remanejamento", valor=Decimal("1"))
    transferencia = Transferencia.objects.create(
        tipo="entre_niveis", allocation_origem=dados["nacional_2"], allocation_destino=dados["estadual_1"],
        valor=Decimal("1"), motivo="x", saldo_origem_antes=0, saldo_origem_depois=0,
        saldo_destino_antes=0, saldo_destino_depois=0,
    )

    apps = _migrar(DEPOIS)

    Pool = apps.get_model("sgp", "BudgetPool")
    pools = Pool.objects.filter(rubrica_id=dados["rubrica"].pk)
    nacional, estadual = pools.get(nivel="nacional"), pools.get(nivel="estadual")
    Transacao = apps.get_model("sgp", "BudgetTransaction")
    assert Transacao.objects.get(pk=transacao_1.pk).pool_id == nacional.pk
    assert Transacao.objects.get(pk=transacao_2.pk).pool_id == nacional.pk
    transferencia = apps.get_model("sgp", "BudgetTransfer").objects.get(pk=transferencia.pk)
    assert transferencia.pool_origem_id == nacional.pk
    assert transferencia.pool_destino_id == estadual.pk


def test_reversao_preserva_a_soma_por_rubrica_e_nivel(banco_antes_da_migracao):
    dados = _alocacoes(banco_antes_da_migracao)
    Transacao = banco_antes_da_migracao.get_model("sgp", "BudgetTransaction")
    transacao = Transacao.objects.create(allocation=dados["nacional_2"], tipo="remanejamento", valor=Decimal("1"))
    _migrar(DEPOIS)

    apps = _migrar(ANTES)

    Alocacao = apps.get_model("sgp", "BudgetAllocation")
    alocacoes = Alocacao.objects.filter(rubrica_id=dados["rubrica"].pk)
    assert alocacoes.get(nivel="nacional").valor_alocado == Decimal("1500")
    territorial = alocacoes.get(nivel="territorial")
    assert territorial.valor_alocado == Decimal("150")
    assert territorial.valor_comprometido == Decimal("40")
    assert territorial.valor_executado == Decimal("10")
    assert Transacao.objects.get(pk=transacao.pk).allocation_id == alocacoes.get(nivel="nacional").pk
