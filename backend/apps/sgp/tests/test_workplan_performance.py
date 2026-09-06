"""
Testes de performance/RNF para a issue #229 (Denormalizar progresso da Ação).

Cobertura (tabela da issue):
    1. test_campo_atualiza_ao_concluir — Atividade -> concluido incrementa o campo
    2. test_campo_decrementa_ao_sair_de_concluido — Reversão decrementa
    3. test_migration_popula_existentes — Valores corretos após a migration
    4. test_comando_reconcilia — Divergência forçada é detectada
    5. test_painel_queries_constantes — Mesmo nº de queries com 5 e com 30 Ações
    6. test_painel_sob_500ms — Dataset de carga; assertiva de tempo
    7. test_listagem_5000_upfs_sob_3s — Dataset de carga; assertiva de tempo
"""
import importlib
from datetime import date, timedelta
from decimal import Decimal
from time import monotonic

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.tests.factories import UserFactory
from apps.sgp.models import UPF, Activity, MembroFamilia, WorkPlanAcao
from apps.sgp.tests.factories import (
    ActivityFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

PANEL_URL = "/api/v1/sgp/plano-trabalho/painel/"


def test_campo_atualiza_ao_concluir():
    acao = WorkPlanAcaoFactory()
    atividade = ActivityFactory(acao=acao, status="em_andamento")
    acao.refresh_from_db(fields=["quantidade_realizada"])
    assert acao.quantidade_realizada == 0

    atividade.status = "concluido"
    atividade.save()

    acao.refresh_from_db(fields=["quantidade_realizada"])
    assert acao.quantidade_realizada == 1


def test_campo_decrementa_ao_sair_de_concluido():
    acao = WorkPlanAcaoFactory()
    atividade = ActivityFactory(acao=acao, status="concluido")
    acao.refresh_from_db(fields=["quantidade_realizada"])
    assert acao.quantidade_realizada == 1

    # "concluido" é estado terminal (STATUS_TRANSITIONS não permite saída) — o
    # único caminho real de uma Atividade concluída deixar de contar é o
    # soft-delete (ativo=False).
    atividade.ativo = False
    atividade.save()

    acao.refresh_from_db(fields=["quantidade_realizada"])
    assert acao.quantidade_realizada == 0


def test_migration_popula_existentes():
    acao = WorkPlanAcaoFactory()
    ActivityFactory(acao=acao, status="concluido")
    ActivityFactory(acao=acao, status="concluido")
    ActivityFactory(acao=acao, status="planejado")

    # Corrompe o campo direto no banco, simulando o estado anterior à migration.
    WorkPlanAcao.objects.filter(pk=acao.pk).update(quantidade_realizada=0)

    migration_module = importlib.import_module(
        "apps.sgp.migrations.0027_popula_quantidade_realizada"
    )
    migration_module.popula_quantidade_realizada(django_apps, None)

    acao.refresh_from_db(fields=["quantidade_realizada"])
    assert acao.quantidade_realizada == 2


def test_comando_reconcilia():
    acao = WorkPlanAcaoFactory()
    ActivityFactory(acao=acao, status="concluido")

    # Força a divergência direto no banco (bypassa o signal).
    WorkPlanAcao.objects.filter(pk=acao.pk).update(quantidade_realizada=999)

    with pytest.raises(CommandError):
        call_command("verificar_progresso_acoes")


def test_painel_queries_constantes(auth_client):
    meta = WorkPlanMetaFactory(numero=1)
    for indice in range(5):
        WorkPlanAcaoFactory(meta=meta, numero=f"1.{indice + 1}")

    with CaptureQueriesContext(connection) as ctx_5:
        response_5 = auth_client.get("/api/v1/metas/")
    queries_com_5 = len(ctx_5.captured_queries)

    for indice in range(5, 30):
        WorkPlanAcaoFactory(meta=meta, numero=f"1.{indice + 1}")

    with CaptureQueriesContext(connection) as ctx_30:
        response_30 = auth_client.get("/api/v1/metas/")
    queries_com_30 = len(ctx_30.captured_queries)

    assert response_5.status_code == 200
    assert response_30.status_code == 200
    assert queries_com_30 == queries_com_5


def test_painel_sob_500ms(auth_client, municipio):
    tecnico = UserFactory()
    inicio = timezone.now()
    fim = inicio + timedelta(hours=4)

    acoes = []
    for numero_meta in range(1, 8):
        meta = WorkPlanMetaFactory(numero=numero_meta)
        for indice in range(30):
            acoes.append(
                WorkPlanAcaoFactory(
                    meta=meta,
                    numero=f"{numero_meta}.{indice + 1}",
                    quantidade_planejada=Decimal("500"),
                )
            )

    atividades = [
        Activity(
            titulo="Atividade de carga",
            tipo_atividade="visita_tecnica",
            acao=acao,
            forma_atuacao="realizacao",
            tecnico_responsavel=tecnico,
            municipio=municipio,
            ambito="municipal",
            data_inicio=inicio,
            data_fim=fim,
            descricao_narrativa="Atividade de carga para teste de performance.",
            status="concluido",
            ativo=True,
        )
        for acao in acoes
        for _ in range(500)
    ]
    Activity.objects.bulk_create(atividades, batch_size=1000)
    # bulk_create não dispara signals — popula o campo materializado manualmente,
    # simulando o estado que o signal manteria em produção.
    WorkPlanAcao.objects.filter(
        pk__in=[acao.pk for acao in acoes]
    ).update(quantidade_realizada=500)

    started_at = monotonic()
    response = auth_client.get(PANEL_URL)
    elapsed = monotonic() - started_at

    assert response.status_code == 200
    assert sum(len(meta["acoes"]) for meta in response.data["metas"]) == 210
    assert elapsed < 0.5


def test_listagem_5000_upfs_sob_3s(auth_client, projeto, municipio, territory):
    titulares = [
        MembroFamilia(
            nome_completo=f"Titular de carga {indice}",
            grau_parentesco="titular",
            cpf=f"{indice:011d}",
            data_nascimento=date(1990, 1, 1),
        )
        for indice in range(5000)
    ]
    MembroFamilia.objects.bulk_create(titulares, batch_size=1000)

    upfs = [
        UPF(
            projeto=projeto,
            municipio=municipio,
            territorio=territory,
            titular=titular,
            ativa=True,
        )
        for titular in titulares
    ]
    UPF.objects.bulk_create(upfs, batch_size=1000)

    for titular, upf in zip(titulares, upfs):
        titular.upf = upf
    MembroFamilia.objects.bulk_update(titulares, ["upf"], batch_size=1000)

    started_at = monotonic()
    response = auth_client.get(f"/api/v1/upfs/?municipio={municipio.pk}&page_size=50")
    elapsed = monotonic() - started_at

    assert response.status_code == 200
    assert len(response.data["results"]) == 50
    assert response.data["count"] == 5000
    assert elapsed < 3
