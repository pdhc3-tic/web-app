"""Nome dos estados por extenso: `seed_core` e a migration que corrige os já gravados."""
import importlib
from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db.models import F

from apps.core.management.commands.seed_core import NOMES_DOS_ESTADOS, ensure_state
from apps.core.models import State

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.core.migrations.0022_nome_dos_estados_por_extenso")


def _estado(sigla, nome):
    state, _ = State.objects.update_or_create(sigla=sigla, defaults={"nome": nome})
    return state


def test_migration_troca_a_sigla_pelo_nome_e_pode_rodar_de_novo():
    rn = _estado("RN", "RN")

    migration.nome_por_extenso(apps, None)
    migration.nome_por_extenso(apps, None)

    rn.refresh_from_db()
    assert rn.nome == "Rio Grande do Norte"


def test_migration_mantem_nome_editado():
    pb = _estado("PB", "Paraíba (sede)")

    migration.nome_por_extenso(apps, None)

    pb.refresh_from_db()
    assert pb.nome == "Paraíba (sede)"


def test_migration_e_seed_usam_a_mesma_lista():
    assert migration.NOMES_DOS_ESTADOS == NOMES_DOS_ESTADOS
    assert len(NOMES_DOS_ESTADOS) == 27


def test_seed_cria_com_o_nome_e_corrige_o_gravado_com_a_sigla():
    State.objects.filter(sigla__in=["CE", "MA"]).delete()
    _estado("MA", "MA")

    ce, criado = ensure_state("CE")
    ma, _ = ensure_state("MA")

    assert (ce.nome, criado) == ("Ceará", True)
    ma.refresh_from_db()
    assert ma.nome == "Maranhão"


def test_seed_mantem_nome_editado():
    _estado("AL", "Alagoas (litoral)")

    al, criado = ensure_state("AL")

    assert (al.nome, criado) == ("Alagoas (litoral)", False)


def test_seed_core_grava_os_estados_por_extenso():
    call_command("seed_core", stdout=StringIO())

    assert State.objects.get(sigla="RN").nome == "Rio Grande do Norte"
    assert not State.objects.filter(nome=F("sigla")).exists()
