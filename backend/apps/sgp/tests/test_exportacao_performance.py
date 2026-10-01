"""
RNF de exportação (SGP §12): relatório de 12 meses em menos de 60 s.

Cobre as duas exportações que o front dispara com período — Plano de Trabalho
e Atividades. Os testes imprimem o tempo medido (rodar com `-s`), que alimenta
a tabela de `backend/docs/performance.md`.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from time import monotonic

import pytest
from django.utils import timezone

from apps.core.tests.factories import UserFactory
from apps.sgp.models import Activity, WorkPlanAcao
from apps.sgp.tests.factories import WorkPlanAcaoFactory, WorkPlanMetaFactory

pytestmark = pytest.mark.django_db

LIMITE_SEGUNDOS = 60
ATIVIDADES_POR_ACAO = 100
PERIODO = {"periodo_inicio": "2026-01-01", "periodo_fim": "2026-12-31"}


@pytest.fixture
def dataset_12_meses(municipio):
    """7 Metas × 30 Ações, com 21.000 Atividades distribuídas pelos 12 meses."""
    tecnico = UserFactory()
    inicio_ano = timezone.make_aware(datetime(2026, 1, 1, 8, 0))

    acoes = []
    for numero_meta in range(1, 8):
        meta = WorkPlanMetaFactory(
            numero=numero_meta, data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31)
        )
        for indice in range(30):
            acoes.append(
                WorkPlanAcaoFactory(
                    meta=meta,
                    numero=f"{numero_meta}.{indice + 1}",
                    quantidade_planejada=Decimal("200"),
                )
            )

    atividades = []
    for acao in acoes:
        for indice in range(ATIVIDADES_POR_ACAO):
            data_inicio = inicio_ano + timedelta(days=(indice * 365) // ATIVIDADES_POR_ACAO)
            atividades.append(
                Activity(
                    titulo="Atividade de carga",
                    tipo_atividade="visita_tecnica",
                    acao=acao,
                    forma_atuacao="realizacao",
                    tecnico_responsavel=tecnico,
                    municipio=municipio,
                    ambito="municipal",
                    data_inicio=data_inicio,
                    data_fim=data_inicio + timedelta(hours=4),
                    descricao_narrativa="Atividade de carga para o RNF de exportação.",
                    status="concluido" if indice % 2 else "planejado",
                    ativo=True,
                )
            )
    Activity.objects.bulk_create(atividades, batch_size=2000)
    WorkPlanAcao.objects.filter(pk__in=[a.pk for a in acoes]).update(
        quantidade_realizada=ATIVIDADES_POR_ACAO // 2
    )
    return len(acoes), len(atividades)


@pytest.mark.parametrize("formato", ["csv", "xlsx"])
def test_exportacao_atividades_12_meses_sob_60s(auth_client, dataset_12_meses, formato):
    _, total_atividades = dataset_12_meses

    started_at = monotonic()
    response = auth_client.get("/api/v1/sgp/atividades/exportar/", {"formato": formato, **PERIODO})
    elapsed = monotonic() - started_at

    print(
        f"\n[RNF] exportação de Atividades, 12 meses ({total_atividades} atividades, "
        f"{formato}): {elapsed:.3f}s (limite {LIMITE_SEGUNDOS}s)"
    )

    assert response.status_code == 200
    assert elapsed < LIMITE_SEGUNDOS


@pytest.mark.parametrize("formato", ["csv", "xlsx"])
def test_exportacao_plano_trabalho_12_meses_sob_60s(auth_client, dataset_12_meses, formato):
    total_acoes, total_atividades = dataset_12_meses

    started_at = monotonic()
    response = auth_client.get("/api/v1/sgp/plano-trabalho/exportar/", {"formato": formato, **PERIODO})
    elapsed = monotonic() - started_at

    print(
        f"\n[RNF] exportação do PT, 12 meses ({total_acoes} ações, {total_atividades} "
        f"atividades, {formato}): {elapsed:.3f}s (limite {LIMITE_SEGUNDOS}s)"
    )

    assert response.status_code == 200
    assert elapsed < LIMITE_SEGUNDOS
