"""Migration que generaliza os riscos de glosa já registrados."""
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.sgd.tests.factories import DemandFactory
from apps.sgp.models import GlosaRisk

ANTES = [("sgp", "0017_ajustes_de_pool_e_limite")]

pytestmark = pytest.mark.django_db(transaction=True)


def _migrar(alvo):
    executor = MigrationExecutor(connection)
    executor.migrate(alvo)
    return MigrationExecutor(connection).loader.project_state(alvo).apps


def _migrar_tudo():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.fixture
def volta_ao_fim():
    yield
    _migrar_tudo()


def test_registros_existentes_viram_pago_acima_com_severidade_alta_e_a_atividade(volta_ao_fim):
    demanda = DemandFactory()
    Antigo = _migrar(ANTES).get_model("sgp", "GlosaRisk")
    Antigo.objects.create(
        demanda_id=str(demanda.pk), demand_request_id="7", valor_autorizado=Decimal("100"),
        valor_pago=Decimal("150"), excedente=Decimal("50"),
    )
    Antigo.objects.create(
        demanda_id="999999999", demand_request_id="8", valor_autorizado=Decimal("100"),
        valor_pago=Decimal("110"), excedente=Decimal("10"),
    )

    _migrar_tudo()

    risco = GlosaRisk.objects.get(demand_request_id="7")
    assert (risco.tipo_situacao, risco.severidade) == (GlosaRisk.Tipo.PAGO_ACIMA_AUTORIZADO, GlosaRisk.Severidade.ALTA)
    assert (risco.entidade, risco.entidade_id) == (GlosaRisk.ENTIDADE_DEMANDA, str(demanda.pk))
    assert risco.activity_id == demanda.activity_id
    assert risco.valor_exposto == Decimal("50.00")
    sem_demanda = GlosaRisk.objects.get(demand_request_id="8")
    assert (sem_demanda.activity_id, sem_demanda.entidade_id) == (None, "999999999")
