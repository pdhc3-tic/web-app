"""O contexto herdado da atividade tem uma fonte única dentro do SGD."""
import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.core.tests.factories import UserFactory
from apps.sgd.services import contexto
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import BudgetRubricaFactory, WorkPlanAcaoFactory

APP_SGD = Path(settings.BASE_DIR) / "apps" / "sgd"
EXCETOS = {APP_SGD / "services" / "contexto.py", APP_SGD / "serializers" / "demand.py"}
PROIBIDO = re.compile(r"acao__meta|municipio__state|activity\.acao\.")


def test_sgd_so_le_o_contexto_da_atividade_por_contexto():
    violacoes = [
        f"{arquivo.relative_to(APP_SGD)}:{numero}: {linha.strip()}"
        for arquivo in APP_SGD.rglob("*.py")
        if arquivo not in EXCETOS and not {"tests", "migrations"} & set(arquivo.relative_to(APP_SGD).parts)
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1)
        if PROIBIDO.search(linha)
    ]
    assert violacoes == []


@pytest.mark.django_db
def test_estado_e_territorio_vem_da_atividade(activity_rn, territory_rn):
    demand = DemandFactory(activity=activity_rn)

    assert contexto.estado_da_demanda(demand) == "RN"
    assert contexto.estado_da_atividade(activity_rn) == "RN"
    assert contexto.territorio_da_demanda(demand) == territory_rn


@pytest.mark.django_db
def test_cadeia_pt_traz_acao_submeta_meta_e_indicador(activity_rn):
    acao = activity_rn.acao

    cadeia = contexto.cadeia_pt(DemandFactory(activity=activity_rn))

    assert (cadeia.acao, cadeia.submeta, cadeia.meta, cadeia.indicador) == (
        acao, acao.submeta, acao.meta, acao.indicador,
    )


@pytest.mark.django_db
def test_rubricas_previstas_vem_da_acao(activity_rn):
    rubrica = BudgetRubricaFactory()
    activity_rn.acao.rubricas_previstas.set([rubrica])

    assert contexto.rubricas_previstas(DemandFactory(activity=activity_rn)) == [rubrica]


@pytest.mark.django_db
def test_participantes_previstos_sem_membros_e_zero(activity_rn):
    assert contexto.participantes_previstos(DemandFactory(activity=activity_rn)) == 0


@pytest.mark.django_db
def test_filtro_por_estado_separa_as_demandas(activity_rn, municipio_ce):
    from apps.sgd.models import Demand
    from apps.sgp.tests.factories import ActivityFactory

    do_rn = DemandFactory(activity=activity_rn)
    DemandFactory(activity=ActivityFactory(municipio=municipio_ce, acao=WorkPlanAcaoFactory()), solicitante=UserFactory())

    assert list(Demand.objects.filter(contexto.filtro_por_estado(["RN"]))) == [do_rn]
