"""Migration que converte cada limite individual em sobrescrita do período corrente."""
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from freezegun import freeze_time

ANTES = [("sgd", "0018_preencher_totais_das_demandas"), ("sgp", "0012_spendinglimit_esquema")]
DEPOIS = [("sgp", "0013_converter_limites_individuais")]

pytestmark = pytest.mark.django_db(transaction=True)


def _migrar(alvo):
    executor = MigrationExecutor(connection)
    executor.migrate(alvo)
    return MigrationExecutor(connection).loader.project_state(alvo).apps


@pytest.fixture
def banco_antes_da_conversao():
    yield _migrar(ANTES)
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _limite_com_saldo(apps, *, email="limite@test.com"):
    User = apps.get_model("core", "User")
    Rubrica = apps.get_model("sgp", "BudgetRubrica")
    Limite = apps.get_model("sgd", "DemandIndividualLimit")
    usuario = User.objects.create(email=email, nome="Limite", password="x")
    rubrica = Rubrica.objects.create(nome="Rubrica da conversão", slug="rubrica-da-conversao")
    limite = Limite.objects.create(
        solicitante=usuario, rubrica=rubrica, valor_limite=Decimal("5000"),
        valor_comprometido=Decimal("0"), valor_executado=Decimal("800"),
    )
    return usuario, rubrica, limite


@freeze_time("2026-11-03")
def test_converte_em_sobrescrita_do_periodo_preservando_saldos(banco_antes_da_conversao):
    usuario, rubrica, _ = _limite_com_saldo(banco_antes_da_conversao)

    apps = _migrar(DEPOIS)

    linha = apps.get_model("sgp", "SpendingLimit").objects.get(user_id=usuario.pk, rubrica_id=rubrica.pk)
    assert linha.escopo == "individual"
    assert linha.herdado is False
    assert linha.justificativa
    assert linha.valor_limite == Decimal("5000")
    assert linha.valor_executado == Decimal("800")
    assert str(linha.periodo_inicio) == "2026-10-01"
    assert str(linha.periodo_fim) == "2026-12-31"


@freeze_time("2026-11-03")
def test_abre_o_ledger_coerente_com_os_saldos(banco_antes_da_conversao):
    usuario, rubrica, _ = _limite_com_saldo(banco_antes_da_conversao)

    apps = _migrar(DEPOIS)

    linha = apps.get_model("sgp", "SpendingLimit").objects.get(user_id=usuario.pk, rubrica_id=rubrica.pk)
    tipos = {
        tipo: valor for tipo, valor in
        apps.get_model("sgp", "BudgetTransaction").objects.filter(spending_limit_id=linha.pk).values_list("tipo", "valor")
    }
    assert tipos == {
        "aumento_limite": Decimal("5000"), "reserva": Decimal("800"), "execucao": Decimal("800"),
    }


@freeze_time("2026-11-03")
def test_reversao_volta_ao_limite_individual_sem_ledger(banco_antes_da_conversao):
    usuario, rubrica, limite = _limite_com_saldo(banco_antes_da_conversao)
    _migrar(DEPOIS)

    apps = _migrar(ANTES)

    Limite = apps.get_model("sgd", "DemandIndividualLimit")
    restaurado = Limite.objects.get(solicitante_id=usuario.pk, rubrica_id=rubrica.pk)
    assert restaurado.valor_limite == Decimal("5000")
    assert restaurado.valor_executado == Decimal("800")
    assert not apps.get_model("sgp", "SpendingLimit").objects.filter(user_id=usuario.pk).exists()
    assert not apps.get_model("sgp", "BudgetTransaction").objects.filter(spending_limit__isnull=False).exists()
