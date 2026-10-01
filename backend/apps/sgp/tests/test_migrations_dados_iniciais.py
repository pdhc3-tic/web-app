"""Migrations do SGP: dados iniciais idempotentes e histórico sem pendências."""
import importlib

import pytest
from django.apps import apps
from django.core.management import call_command

from apps.sgp.models import BudgetRubrica, Cultura, EspecieAnimal, Indicator

pytestmark = pytest.mark.django_db

seed = importlib.import_module("apps.sgp.migrations.0002_seed_dados_iniciais")


def _semear():
    seed.forwards(apps, None)


def test_semeia_catalogos_rubricas_e_indicadores():
    _semear()

    assert Cultura.objects.count() >= len(seed.CULTURAS)
    assert EspecieAnimal.objects.count() >= len(seed.ESPECIES_ANIMAIS)
    assert set(BudgetRubrica.objects.values_list("slug", flat=True)) >= {
        r["slug"] for r in seed.RUBRICAS
    }
    assert set(Indicator.objects.values_list("codigo", flat=True)) >= {
        i[0] for i in seed.INDICADORES
    }


def test_rodar_de_novo_nao_duplica():
    _semear()
    antes = (
        Cultura.objects.count(),
        EspecieAnimal.objects.count(),
        BudgetRubrica.objects.count(),
        Indicator.objects.count(),
    )

    _semear()

    assert antes == (
        Cultura.objects.count(),
        EspecieAnimal.objects.count(),
        BudgetRubrica.objects.count(),
        Indicator.objects.count(),
    )


def test_indicador_ajustado_pela_ugp_sobrevive_a_nova_execucao():
    _semear()
    Indicator.objects.filter(codigo="IND-OFI").update(nome="Oficina ajustada", ativo=False)

    _semear()

    indicador = Indicator.objects.get(codigo="IND-OFI")
    assert indicador.nome == "Oficina ajustada"
    assert indicador.ativo is False


def test_models_sem_migration_pendente():
    # Com mudança de model sem migration, o comando termina com SystemExit(1).
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
