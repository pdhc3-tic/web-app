"""A renomeação preserva os dados e chega aos nomes da Arquitetura, nos dois sentidos."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.sgp.models import UFPA, Activity, MembroFamilia
from apps.sgp.tests.factories import ActivityFactory, MembroFactory, UFPAFactory

ANTES = [("sgp", "0020_valores_monetarios_em_14_digitos")]

pytestmark = pytest.mark.django_db(transaction=True)


def _migrar(alvo):
    executor = MigrationExecutor(connection)
    executor.migrate(alvo)
    return MigrationExecutor(connection).loader.project_state(alvo).apps


def _migrar_tudo():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _colunas(tabela):
    with connection.cursor() as cursor:
        return {coluna.name for coluna in connection.introspection.get_table_description(cursor, tabela)}


@pytest.fixture
def volta_ao_fim():
    yield
    _migrar_tudo()


def test_dados_sobrevivem_a_voltar_e_reaplicar(volta_ao_fim):
    ufpa = UFPAFactory()
    membro = MembroFactory(ufpa=ufpa)
    atividade = ActivityFactory()
    atividade.ufpas_participantes.add(ufpa)

    antigos = _migrar(ANTES)

    assert antigos.get_model("sgp", "UPF")._base_manager.filter(pk=ufpa.pk).exists()
    assert antigos.get_model("sgp", "MembroFamilia")._base_manager.get(pk=membro.pk).upf_id == ufpa.pk
    assert antigos.get_model("sgp", "Activity")._base_manager.get(pk=atividade.pk).upfs_participantes.filter(
        pk=ufpa.pk,
    ).exists()

    _migrar_tudo()

    assert UFPA.all_objects.filter(pk=ufpa.pk).exists()
    assert MembroFamilia.objects.get(pk=membro.pk).ufpa_id == ufpa.pk
    assert Activity.objects.get(pk=atividade.pk).ufpas_participantes.filter(pk=ufpa.pk).exists()


def test_tabelas_e_colunas_com_os_nomes_novos():
    with connection.cursor() as cursor:
        tabelas = set(connection.introspection.table_names(cursor))

    assert {"sgp_ufpa", "sgp_ufpadocument", "sgp_activityufpa"} <= tabelas
    assert not {"sgp_upf", "sgp_upfdocument", "sgp_activity_upfs_participantes"} & tabelas
    assert "ufpa_id" in _colunas("sgp_activityufpa")
    for tabela in ("sgp_membrofamilia", "sgp_production", "sgp_formresponse", "sgp_ufpadocument"):
        assert "ufpa_id" in _colunas(tabela)
        assert "upf_id" not in _colunas(tabela)
