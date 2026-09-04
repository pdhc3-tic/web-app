"""
Testes para GET /api/v1/sgp/atividades/calendario/ — Issue #126.

Cobertura:
    1. Filtro por intervalo de 1 semana → apenas atividades dentro do range
    2. Filtro combinado tecnico_id + status → restringe corretamente
    3. Intervalo de 120 dias → 400 com code CALENDAR_INTERVAL_TOO_LARGE
    4. N+1: endpoint não gera queries adicionais ao expandir técnico responsável
    5. Sem parâmetros → 400 com erros de campo obrigatório
    6. fim < inicio → 400
    7. Payload contém todos os campos esperados (id, titulo, status, cor, data_inicio, data_fim,
       tipo_atividade, atrasada, tecnico_responsavel, municipio)
    8. RLS: usuário ADT não vê atividades fora do seu território
"""
import datetime
from unittest.mock import patch

import pytest
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
    MunicipalityFactory,
)
from apps.sgp.tests.factories import ActivityFactory
from django.utils import timezone
import datetime


CALENDARIO_URL = "/api/v1/sgp/atividades/calendario/"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def state_rn(db):
    return StateFactory(sigla="RN", nome="Rio Grande do Norte")


@pytest.fixture
def state_ce(db):
    return StateFactory(sigla="CE", nome="Ceará")


@pytest.fixture
def territory_rn(db, state_rn):
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def territory_ce(db, state_ce):
    return TerritoryFactory(nome="Território CE", estados=["CE"])


@pytest.fixture
def municipio_rn(db, state_rn, territory_rn):
    return MunicipalityFactory(
        nome="Mossoró", state=state_rn, territory=territory_rn, codigo_ibge="2408003"
    )


@pytest.fixture
def municipio_ce(db, state_ce, territory_ce):
    return MunicipalityFactory(
        nome="Fortaleza", state=state_ce, territory=territory_ce, codigo_ibge="2304400"
    )


@pytest.fixture
def usuario_ugp(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="UGP User", profiles=[(role, None)])


@pytest.fixture
def tecnico_a(db):
    role = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    return UserFactory(email="tec_a@test.com", nome="Técnico A", profiles=[(role, None)])


@pytest.fixture
def tecnico_b(db):
    role = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    return UserFactory(email="tec_b@test.com", nome="Técnico B", profiles=[(role, None)])


@pytest.fixture
def usuario_adt_rn(db, territory_rn):
    role = RoleFactory(slug="adt-acr", nome="ADT")
    return UserFactory(
        email="adt_rn@test.com", nome="ADT RN", profiles=[(role, territory_rn)]
    )


@pytest.fixture
def auth_ugp(api_client, usuario_ugp):
    api_client.force_authenticate(user=usuario_ugp)
    return api_client


@pytest.fixture
def auth_adt_rn(api_client, usuario_adt_rn):
    api_client.force_authenticate(user=usuario_adt_rn)
    return api_client

def aware_dt(year, month, day, hour=0, minute=0):
    return timezone.make_aware(datetime.datetime(year, month, day, hour, minute))

# ===========================================================================
# Teste 1 — Filtro por intervalo de 1 semana
# ===========================================================================

@pytest.mark.django_db
def test_calendario_retorna_apenas_atividades_dentro_do_intervalo(auth_ugp, municipio_rn):
    """
    Apenas atividades cujo (data_inicio, data_fim) intersecciona com o range
    devem aparecer. Atividades totalmente fora do intervalo são excluídas.
    """
    # Dentro: inicia dentro da semana
    dentro = ActivityFactory(
        municipio=municipio_rn,
        data_inicio=aware_dt(2026, 8, 3),
        data_fim=aware_dt(2026, 8, 5),
        status="planejado",
    )
    # Dentro: abrange toda a semana (multi-dia)
    abrange = ActivityFactory(
        municipio=municipio_rn,
        data_inicio=aware_dt(2026, 7, 28),
        data_fim=aware_dt(2026, 8, 10),
        status="em_andamento",
    )
    # Fora: terminou antes da semana
    antes = ActivityFactory(
        municipio=municipio_rn,
        data_inicio=aware_dt(2026, 7, 20),
        data_fim=aware_dt(2026, 7, 31),
        status="concluido",
    )
    # Fora: começa depois da semana
    depois = ActivityFactory(
        municipio=municipio_rn,
        data_inicio=aware_dt(2026, 8, 15),
        data_fim=aware_dt(2026, 8, 20),
        status="planejado",
    )

    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-01", "fim": "2026-08-07"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.data

    ids = {item["id"] for item in resp.data["results"]}
    assert dentro.pk in ids, "Atividade dentro da semana deve aparecer"
    assert abrange.pk in ids, "Atividade que abrange a semana deve aparecer"
    assert antes.pk not in ids, "Atividade anterior ao intervalo não deve aparecer"
    assert depois.pk not in ids, "Atividade posterior ao intervalo não deve aparecer"

    assert resp.data["count"] == len(resp.data["results"])
    assert resp.data["inicio"] == "2026-08-01"
    assert resp.data["fim"] == "2026-08-07"


# ===========================================================================
# Teste 2 — Filtro combinado tecnico_id + status
# ===========================================================================

@pytest.mark.django_db
def test_calendario_filtro_combinado_tecnico_e_status(
    auth_ugp, municipio_rn, tecnico_a, tecnico_b
):
    """
    Ao combinar tecnico_id e status, apenas atividades que satisfaçam
    ambos os critérios devem aparecer.
    """
    # Corresponde a ambos os filtros
    alvo = ActivityFactory(
        municipio=municipio_rn,
        tecnico_responsavel=tecnico_a,
        status="agendado",
        data_inicio=aware_dt(2026, 8, 1),
        data_fim=aware_dt(2026, 8, 3),
    )
    # Mesmo técnico, status diferente
    mesmo_tec_outro_status = ActivityFactory(
        municipio=municipio_rn,
        tecnico_responsavel=tecnico_a,
        status="planejado",
        data_inicio=aware_dt(2026, 8, 1),
        data_fim=aware_dt(2026, 8, 3),
    )
    # Status correto, técnico diferente
    outro_tec_mesmo_status = ActivityFactory(
        municipio=municipio_rn,
        tecnico_responsavel=tecnico_b,
        status="agendado",
        data_inicio=aware_dt(2026, 8, 1),
        data_fim=aware_dt(2026, 8, 3),
    )

    resp = auth_ugp.get(
        CALENDARIO_URL,
        {
            "inicio": "2026-08-01",
            "fim": "2026-08-07",
            "tecnico_id": tecnico_a.pk,
            "status": "agendado",
        },
    )
    assert resp.status_code == status.HTTP_200_OK, resp.data

    ids = {item["id"] for item in resp.data["results"]}
    assert alvo.pk in ids
    assert mesmo_tec_outro_status.pk not in ids
    assert outro_tec_mesmo_status.pk not in ids


# ===========================================================================
# Teste 3 — Intervalo de 120 dias → 400
# ===========================================================================

@pytest.mark.django_db
def test_calendario_intervalo_120_dias_retorna_400(auth_ugp):
    """Intervalo > 90 dias deve retornar 400 com code CALENDAR_INTERVAL_TOO_LARGE."""
    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-01-01", "fim": "2026-05-01"},  # 120 dias
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.data
    assert resp.data.get("code") == "CALENDAR_INTERVAL_TOO_LARGE"
    assert "120" in str(resp.data.get("detail", ""))


@pytest.mark.django_db
def test_calendario_exatamente_90_dias_aceito(auth_ugp, municipio_rn):
    """Intervalo de exatamente 90 dias deve ser aceito (limite é > 90, não >= 90)."""
    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-06-01", "fim": "2026-08-30"},  # 90 dias exatos
    )
    assert resp.status_code == status.HTTP_200_OK, resp.data


@pytest.mark.django_db
def test_calendario_sem_parametros_retorna_400(auth_ugp):
    """Chamada sem 'inicio' e 'fim' deve retornar 400 com erros por campo."""
    resp = auth_ugp.get(CALENDARIO_URL)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "inicio" in resp.data
    assert "fim" in resp.data


@pytest.mark.django_db
def test_calendario_fim_antes_de_inicio_retorna_400(auth_ugp):
    """fim < inicio deve retornar 400."""
    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-31", "fim": "2026-08-01"},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "fim" in resp.data


# ===========================================================================
# Teste 4 — Sem N+1: assertNumQueries
# ===========================================================================

@pytest.mark.django_db
def test_calendario_sem_n_mais_1_queries(auth_ugp, municipio_rn, tecnico_a, tecnico_b):
    """
    Com 10 atividades de diferentes técnicos, o endpoint deve executar
    um número fixo de queries (select_related elimina o N+1).
    Threshold conservador: ≤ 8 queries independentemente do volume de dados.
    """
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    for i, tec in enumerate([tecnico_a, tecnico_b] * 5):
        ActivityFactory(
            municipio=municipio_rn,
            tecnico_responsavel=tec,
            status="planejado",
            data_inicio=aware_dt(2026, 8, 1) + datetime.timedelta(days=i),
            data_fim=aware_dt(2026, 8, 1) + datetime.timedelta(days=i),
        )

    with CaptureQueriesContext(connection) as ctx:
        resp = auth_ugp.get(
            CALENDARIO_URL,
            {"inicio": "2026-08-01", "fim": "2026-08-31"},
        )

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data["results"]) == 10

    num_queries = len(ctx.captured_queries)
    # Expectativa: 1 query de auth + 1 RLS check + 1 count + 1 SELECT principal = ~4-6
    assert num_queries <= 8, (
        f"Esperado ≤ 8 queries, mas {num_queries} foram executadas. "
        f"Verifique se há N+1 no serializer.\n"
        f"Queries:\n" + "\n".join(q["sql"][:120] for q in ctx.captured_queries)
    )


# ===========================================================================
# Teste 5 — Payload contém os campos esperados
# ===========================================================================

@pytest.mark.django_db
def test_calendario_payload_campos_corretos(auth_ugp, municipio_rn, tecnico_a):
    """Cada item do resultado deve conter exatamente os campos definidos no serializer."""
    ActivityFactory(
        municipio=municipio_rn,
        tecnico_responsavel=tecnico_a,
        status="agendado",
        data_inicio=aware_dt(2026, 8, 5),
        data_fim=aware_dt(2026, 8, 5),
    )

    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-01", "fim": "2026-08-07"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data["results"]) == 1

    item = resp.data["results"][0]

    # Campos obrigatórios no payload
    campos_esperados = [
        "id", "titulo", "tipo_atividade", "tipo_atividade_display",
        "status", "status_display", "atrasada", "cor",
        "data_inicio", "data_fim",
        "tecnico_responsavel", "municipio", "comunidade",
    ]
    for campo in campos_esperados:
        assert campo in item, f"Campo '{campo}' ausente no payload do calendário"

    # cor deve ser uma cor HEX válida
    assert item["cor"].startswith("#"), f"'cor' deve ser um valor HEX, recebido: {item['cor']}"
    assert len(item["cor"]) == 7

    # tecnico_responsavel deve ter id e nome
    assert "id" in item["tecnico_responsavel"]
    assert "nome" in item["tecnico_responsavel"]
    assert "email" not in item["tecnico_responsavel"], (
        "'email' não deve aparecer no payload reduzido do calendário"
    )

    # municipio deve ter id, nome e estado
    assert "id" in item["municipio"]
    assert "nome" in item["municipio"]
    assert "estado" in item["municipio"]


@pytest.mark.django_db
def test_calendario_municipio_inclui_estado(auth_ugp, municipio_rn, tecnico_a):
    """municipio no payload do calendário deve trazer estado {id, sigla, nome}."""
    ActivityFactory(
        municipio=municipio_rn,
        tecnico_responsavel=tecnico_a,
        status="agendado",
        data_inicio=aware_dt(2026, 8, 5),
        data_fim=aware_dt(2026, 8, 5),
    )

    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-01", "fim": "2026-08-07"},
    )
    assert resp.status_code == status.HTTP_200_OK

    item = resp.data["results"][0]
    assert item["municipio"]["estado"]["sigla"] == "RN"


# ===========================================================================
# Teste 6 — Cores semânticas corretas por status
# ===========================================================================

@pytest.mark.django_db
def test_calendario_cor_semantica_por_status(auth_ugp, municipio_rn):
    """Cada status deve gerar a cor HEX correta do design system."""
    from apps.sgp.serializers import STATUS_COR_MAP

    status_testados = [
        ("planejado", "#6B7280"),
        ("agendado", "#3B82F6"),
        ("em_andamento", "#F59E0B"),
        ("concluido", "#10B981"),
        ("adiada", "#8B5CF6"),
        ("nao_realizada", "#EF4444"),
        ("cancelada", "#9CA3AF"),
    ]

    for st, cor_esperada in status_testados:
        ActivityFactory(
            municipio=municipio_rn,
            status=st,
            data_inicio=aware_dt(2026, 8, 1),
            data_fim=aware_dt(2026, 8, 1),
        )

    resp = auth_ugp.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-01", "fim": "2026-08-07"},
    )
    assert resp.status_code == status.HTTP_200_OK

    cores_por_status = {item["status"]: item["cor"] for item in resp.data["results"]}
    for st, cor_esperada in status_testados:
        assert cores_por_status.get(st) == cor_esperada, (
            f"Status '{st}': esperada cor {cor_esperada}, recebida {cores_por_status.get(st)}"
        )


# ===========================================================================
# Teste 7 — RLS: usuário ADT não vê atividades de outro território
# ===========================================================================

@pytest.mark.django_db
def test_calendario_rls_adt_nao_ve_outro_territorio(
    auth_adt_rn, municipio_rn, municipio_ce
):
    """ADT do território RN não deve ver atividades do território CE no calendário."""
    a_rn = ActivityFactory(
        municipio=municipio_rn,
        status="planejado",
        data_inicio=aware_dt(2026, 8, 1),
        data_fim=aware_dt(2026, 8, 5),
    )
    a_ce = ActivityFactory(
        municipio=municipio_ce,
        status="planejado",
        data_inicio=aware_dt(2026, 8, 1),
        data_fim=aware_dt(2026, 8, 5),
    )

    resp = auth_adt_rn.get(
        CALENDARIO_URL,
        {"inicio": "2026-08-01", "fim": "2026-08-07"},
    )
    assert resp.status_code == status.HTTP_200_OK

    ids = {item["id"] for item in resp.data["results"]}
    assert a_rn.pk in ids, "Atividade do próprio território deve aparecer"
    assert a_ce.pk not in ids, "Atividade de outro território não deve aparecer"
