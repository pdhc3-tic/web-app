"""
Testes para o endpoint /api/v1/sgp/atividades/ (Issue #124).

Cobertura:
    1. Criação com campos obrigatórios → 201
    2. Criação sem campos obrigatórios → 400 com field_errors
    3. Transição de status inválida → 400 com code VALIDATION_ERROR
    4. status='concluido' sem evidência → 400
    5. status='cancelada' sem justificativa → 400
    6. Campo atrasada=True quando data_fim passada e status não terminal
    7. RLS: usuário território A não acessa atividade do território B
    8. Paginação: >20 registros retorna count/next/previous/results

Endpoint de detalhe consolidado (Issue #227):
    9.  Detalhe traz fotos e documentos no payload
    10. Fotos ordenadas com capa (ordem=0) primeiro
    11. transicoes_permitidas coerente com STATUS_TRANSITIONS
    12. Sem N+1: número de queries constante com 1 e com 10 fotos
    13. Escopo territorial: ADT de outro território → 404
    14. Atividade inativa (soft-deleted) → 404
"""
import datetime
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
    MunicipalityFactory,
)
from apps.sgp.models import Activity, ActivityDocument, ActivityPhoto
from apps.sgp.models.activity import STATUS_TRANSITIONS
from apps.sgp.tests.factories import ActivityFactory, WorkPlanAcaoFactory
from django.utils import timezone
import datetime


# ---------------------------------------------------------------------------
# Fixtures locais
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
        nome="Mossoró",
        state=state_rn,
        territory=territory_rn,
        codigo_ibge="2408003",
    )


@pytest.fixture
def municipio_ce(db, state_ce, territory_ce):
    return MunicipalityFactory(
        nome="Fortaleza",
        state=state_ce,
        territory=territory_ce,
        codigo_ibge="2304400",
    )


@pytest.fixture
def acao(db):
    return WorkPlanAcaoFactory()


@pytest.fixture
def tecnico(db):
    role = RoleFactory(slug="adt-acr", nome="ADT/ACR")
    return UserFactory(nome="Técnico Teste", profiles=[(role, None)])


# Usuário UGP (acesso global — sem RLS)
@pytest.fixture
def usuario_ugp(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="UGP User", profiles=[(role, None)])


# Usuário ADT vinculado ao território RN
@pytest.fixture
def usuario_adt_rn(db, territory_rn):
    role = RoleFactory(slug="adt-acr", nome="ADT")
    return UserFactory(
        email="adt_rn@test.com",
        nome="ADT RN",
        profiles=[(role, territory_rn)],
    )


# Usuário ADT vinculado ao território CE
@pytest.fixture
def usuario_adt_ce(db, territory_ce):
    role = RoleFactory(slug="adt-acr", nome="ADT")
    return UserFactory(
        email="adt_ce@test.com",
        nome="ADT CE",
        profiles=[(role, territory_ce)],
    )


@pytest.fixture
def auth_ugp(api_client, usuario_ugp):
    api_client.force_authenticate(user=usuario_ugp)
    return api_client


@pytest.fixture
def auth_adt_rn(api_client, usuario_adt_rn):
    api_client.force_authenticate(user=usuario_adt_rn)
    return api_client


@pytest.fixture
def auth_adt_ce(api_client, usuario_adt_ce):
    api_client.force_authenticate(user=usuario_adt_ce)
    return api_client


@pytest.fixture
def payload_minimo(acao, tecnico, municipio_rn):
    """Payload com todos os campos obrigatórios preenchidos."""
    return {
        "titulo": "Visita técnica em Mossoró",
        "tipo_atividade": "visita_tecnica",
        "acao": acao.pk,
        "forma_atuacao": "realizacao",
        "tecnico_responsavel": tecnico.pk,
        "municipio": municipio_rn.pk,
        "ambito": "municipal",
        "data_inicio": "2026-08-01T08:00:00-03:00",
        "data_fim": "2026-08-01T12:00:00-03:00",
        "descricao_narrativa": "Narrativa completa da visita técnica.",
    }


LIST_URL = "/api/v1/sgp/atividades/"


def detail_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/"

def aware_dt(year, month, day, hour=0, minute=0):
    return timezone.make_aware(datetime.datetime(year, month, day, hour, minute))

# ===========================================================================
# Teste 1 — Criação com campos obrigatórios → 201
# ===========================================================================

@pytest.mark.django_db
def test_criar_atividade_campos_obrigatorios_retorna_201(auth_ugp, payload_minimo):
    """Criação com payload mínimo válido deve retornar 201 e persistir o registro."""
    response = auth_ugp.post(LIST_URL, data=payload_minimo, format="json")
    assert response.status_code == status.HTTP_201_CREATED, response.data

    data = response.data
    assert data["titulo"] == payload_minimo["titulo"]
    assert data["status"] == "planejado"
    assert data["ativo"] is True
    assert Activity.objects.filter(pk=data["id"]).exists()


# ===========================================================================
# Teste 2 — Criação sem campos obrigatórios → 400 com field_errors
# ===========================================================================

@pytest.mark.django_db
def test_criar_atividade_sem_campos_obrigatorios_retorna_400(auth_ugp):
    """POST com payload vazio deve retornar 400 com erros por campo."""
    response = auth_ugp.post(LIST_URL, data={}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    erros = response.data
    campos_obrigatorios = [
        "titulo", "tipo_atividade", "acao", "forma_atuacao",
        "tecnico_responsavel", "municipio", "ambito",
        "data_inicio", "data_fim", "descricao_narrativa",
    ]
    for campo in campos_obrigatorios:
        assert campo in erros, (
            f"Campo '{campo}' deveria estar em field_errors, mas não está. Erros: {erros}"
        )


# ===========================================================================
# Teste 3 — Transição de status inválida → 400 com code VALIDATION_ERROR
# ===========================================================================

@pytest.mark.django_db
def test_transicao_status_invalida_retorna_400(auth_ugp, municipio_rn):
    """Planejado → Concluído direto deve retornar 400."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="planejado",
    )

    response = auth_ugp.patch(
        detail_url(atividade.pk),
        data={"status": "concluido"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    erros = response.data
    # O serializer emite o erro dentro de "status" ou no nível raiz
    status_erros = erros.get("status") or erros.get("non_field_errors", [])
    assert status_erros, f"Esperava erros de status, recebi: {erros}"

    # Verifica presença do código de erro
    resposta_str = str(erros)
    assert "VALIDATION_ERROR" in resposta_str or "Transição inválida" in resposta_str


# ===========================================================================
# Teste 4 — status='concluido' sem evidência → 400
# ===========================================================================

@pytest.mark.django_db
def test_concluir_sem_evidencia_retorna_400(auth_ugp, municipio_rn):
    """Transição para 'concluido' sem evidência vinculada deve ser bloqueada."""
    # Criar atividade já em 'em_andamento' (estado pré-concluído válido)
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="em_andamento",
    )

    # has_evidencias() retorna False por padrão (BE-2 stub)
    response = auth_ugp.patch(
        detail_url(atividade.pk),
        data={"status": "concluido"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    resposta_str = str(response.data)
    assert "evidência" in resposta_str or "evidencia" in resposta_str.lower()


@pytest.mark.django_db
def test_concluir_com_evidencia_retorna_200(auth_ugp, municipio_rn):
    """Com has_evidencias() retornando True, transição para 'concluido' deve ser permitida."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="em_andamento",
    )

    with patch.object(Activity, "has_evidencias", return_value=True):
        response = auth_ugp.patch(
            detail_url(atividade.pk),
            data={"status": "concluido"},
            format="json",
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "concluido"


# ===========================================================================
# Teste 5 — status='cancelada' sem justificativa → 400
# ===========================================================================

@pytest.mark.django_db
def test_cancelar_sem_justificativa_retorna_400(auth_ugp, municipio_rn):
    """PATCH para status='cancelada' sem justificativa deve retornar 400."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="agendado",
    )

    response = auth_ugp.patch(
        detail_url(atividade.pk),
        data={"status": "cancelada"},  # sem justificativa
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "justificativa" in response.data


@pytest.mark.django_db
def test_nao_realizada_sem_justificativa_retorna_400(auth_ugp, municipio_rn):
    """PATCH para status='nao_realizada' sem justificativa deve retornar 400."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="em_andamento",
    )

    response = auth_ugp.patch(
        detail_url(atividade.pk),
        data={"status": "nao_realizada"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "justificativa" in response.data


@pytest.mark.django_db
def test_cancelar_com_justificativa_retorna_200(auth_ugp, municipio_rn):
    """PATCH para status='cancelada' com justificativa deve ser aceito."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="agendado",
    )

    response = auth_ugp.patch(
        detail_url(atividade.pk),
        data={
            "status": "cancelada",
            "justificativa": "Falta de recursos para execução.",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "cancelada"


# ===========================================================================
# Teste 6 — atrasada=True quando data_fim no passado e status não terminal
# ===========================================================================

@pytest.mark.django_db
def test_campo_atrasada_true_quando_data_fim_passada(auth_ugp, municipio_rn):
    """Atividade com data_fim no passado e status='agendado' deve ter atrasada=True."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="agendado",
        data_inicio=aware_dt(2025, 1, 1),
        data_fim=aware_dt(2025, 1, 31),  # passado
    )

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["atrasada"] is True


@pytest.mark.django_db
def test_campo_atrasada_false_quando_status_terminal(auth_ugp, municipio_rn):
    """Atividade com data_fim no passado mas status='concluido' deve ter atrasada=False."""
    atividade = ActivityFactory(
        municipio=municipio_rn,
        status="concluido",
        data_inicio=aware_dt(2025, 1, 1),
        data_fim=aware_dt(2025, 1, 31),
    )

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["atrasada"] is False


@pytest.mark.django_db
def test_atividade_inclui_estado(auth_ugp, municipio_rn):
    atividade = ActivityFactory(municipio=municipio_rn)

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["municipio"]["estado"]["sigla"] == "RN"


@pytest.mark.django_db
def test_atividade_list_inclui_estado(auth_ugp, municipio_rn):
    """Mesmo tratamento de município+estado do detail deve valer na listagem."""
    ActivityFactory(municipio=municipio_rn)

    response = auth_ugp.get(LIST_URL)
    assert response.status_code == status.HTTP_200_OK

    item = response.data["results"][0]
    assert item["municipio"]["id"] == municipio_rn.pk
    assert item["municipio"]["nome"] == municipio_rn.nome
    assert item["municipio"]["estado"]["sigla"] == "RN"
    assert "municipio_nome" not in item


# ===========================================================================
# Teste 7 — RLS: território A não vê/edita atividade do território B
# ===========================================================================

@pytest.mark.django_db
def test_rls_usuario_territorio_a_nao_ve_atividade_territorio_b(
    auth_adt_rn, municipio_ce, usuario_adt_rn
):
    """
    Usuário ADT vinculado a território RN não deve listar nem detalhar
    atividade criada no município do território CE.
    """
    atividade_ce = ActivityFactory(
        municipio=municipio_ce,
        tecnico_responsavel=usuario_adt_rn,
        status="planejado",
    )

    # Listagem: atividade não deve aparecer
    response_list = auth_adt_rn.get(LIST_URL)
    assert response_list.status_code == status.HTTP_200_OK
    ids_listados = [item["id"] for item in response_list.data["results"]]
    assert atividade_ce.pk not in ids_listados, (
        "Atividade do território CE não deveria aparecer para usuário RN."
    )

    # Detalhe: deve retornar 404 (queryset filtra antes do get_object)
    response_detail = auth_adt_rn.get(detail_url(atividade_ce.pk))
    assert response_detail.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_rls_ugp_ve_todas_atividades(auth_ugp, municipio_rn, municipio_ce):
    """UGP deve enxergar atividades de todos os territórios."""
    a_rn = ActivityFactory(municipio=municipio_rn, status="planejado")
    a_ce = ActivityFactory(municipio=municipio_ce, status="planejado")

    response = auth_ugp.get(LIST_URL)
    assert response.status_code == status.HTTP_200_OK

    ids = [item["id"] for item in response.data["results"]]
    assert a_rn.pk in ids
    assert a_ce.pk in ids


# ===========================================================================
# Teste 8 — Paginação: >20 registros retorna count/next/previous/results
# ===========================================================================

@pytest.mark.django_db
def test_paginacao_mais_de_20_registros(auth_ugp, municipio_rn):
    """Listagem com >20 registros deve retornar estrutura paginada."""
    # Criar 25 atividades
    for i in range(25):
        ActivityFactory(
            municipio=municipio_rn,
            titulo=f"Atividade Paginação {i:02d}",
            status="planejado",
        )

    response = auth_ugp.get(LIST_URL)
    assert response.status_code == status.HTTP_200_OK

    data = response.data
    assert "count" in data, "Resposta deve conter 'count'"
    assert "next" in data, "Resposta deve conter 'next'"
    assert "previous" in data, "Resposta deve conter 'previous'"
    assert "results" in data, "Resposta deve conter 'results'"

    assert data["count"] >= 25
    assert len(data["results"]) == 20  # page_size padrão
    assert data["next"] is not None  # existe próxima página
    assert data["previous"] is None  # primeira página não tem anterior


@pytest.mark.django_db
def test_paginacao_segunda_pagina(auth_ugp, municipio_rn):
    """Segunda página deve retornar os registros restantes."""
    for i in range(25):
        ActivityFactory(
            municipio=municipio_rn,
            titulo=f"Atividade Pág2 {i:02d}",
            status="planejado",
        )

    response = auth_ugp.get(f"{LIST_URL}?page=2")
    assert response.status_code == status.HTTP_200_OK

    data = response.data
    assert len(data["results"]) >= 5
    assert data["previous"] is not None


# ===========================================================================
# Issue #227 — Endpoint de detalhe consolidado da Atividade
# ===========================================================================

# Teste 9 — Detalhe traz fotos e documentos no payload
# ===========================================================================

@pytest.mark.django_db
def test_detalhe_traz_evidencias(auth_ugp, municipio_rn):
    """Uma única chamada ao detalhe deve retornar fotos e documentos vinculados."""
    atividade = ActivityFactory(municipio=municipio_rn)
    ActivityPhoto.objects.create(
        activity=atividade,
        arquivo_key=f"atividades/{atividade.pk}/fotos/foto.jpg",
        arquivo_url="https://cdn.example.com/foto.jpg",
        ordem=0,
        ativa=True,
    )
    ActivityDocument.objects.create(
        activity=atividade,
        arquivo_key=f"atividades/{atividade.pk}/documentos/doc.pdf",
        arquivo_url="https://cdn.example.com/doc.pdf",
        tipo=ActivityDocument.TIPO_ATA,
        nome_original="ata.pdf",
        data_documento=datetime.date(2026, 8, 1),
        ativo=True,
    )

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK

    assert len(response.data["fotos"]) == 1
    assert response.data["fotos"][0]["arquivo_url"] == "https://cdn.example.com/foto.jpg"

    assert len(response.data["documentos"]) == 1
    assert response.data["documentos"][0]["nome_original"] == "ata.pdf"


# ===========================================================================
# Teste 10 — Fotos ordenadas com capa (ordem=0) primeiro
# ===========================================================================

@pytest.mark.django_db
def test_fotos_ordenadas_capa_primeiro(auth_ugp, municipio_rn):
    """Fotos devem vir ordenadas por `ordem` crescente, capa (ordem=0) primeiro."""
    atividade = ActivityFactory(municipio=municipio_rn)
    for ordem in (2, 0, 1):
        ActivityPhoto.objects.create(
            activity=atividade,
            arquivo_key=f"atividades/{atividade.pk}/fotos/foto{ordem}.jpg",
            arquivo_url=f"https://cdn.example.com/foto{ordem}.jpg",
            ordem=ordem,
            ativa=True,
        )

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK

    ordens = [foto["ordem"] for foto in response.data["fotos"]]
    assert ordens == [0, 1, 2]


# ===========================================================================
# Teste 11 — transicoes_permitidas coerente com STATUS_TRANSITIONS
# ===========================================================================

@pytest.mark.django_db
@pytest.mark.parametrize("status_atual", ["planejado", "agendado", "em_andamento", "concluido"])
def test_transicoes_permitidas(auth_ugp, municipio_rn, status_atual):
    """transicoes_permitidas deve refletir exatamente STATUS_TRANSITIONS do status atual."""
    atividade = ActivityFactory(municipio=municipio_rn, status=status_atual)

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["transicoes_permitidas"] == sorted(STATUS_TRANSITIONS[status_atual])


# ===========================================================================
# Teste 12 — Sem N+1: queries constantes com 1 e com 10 fotos
# ===========================================================================

@pytest.mark.django_db
def test_sem_n_mais_um(auth_ugp, municipio_rn):
    """Número de queries do detalhe deve ser constante independente do nº de fotos."""
    atividade_1_foto = ActivityFactory(municipio=municipio_rn)
    ActivityPhoto.objects.create(
        activity=atividade_1_foto,
        arquivo_key=f"atividades/{atividade_1_foto.pk}/fotos/foto.jpg",
        arquivo_url="https://cdn.example.com/foto.jpg",
        ordem=0,
        ativa=True,
    )

    atividade_10_fotos = ActivityFactory(municipio=municipio_rn)
    for i in range(10):
        ActivityPhoto.objects.create(
            activity=atividade_10_fotos,
            arquivo_key=f"atividades/{atividade_10_fotos.pk}/fotos/foto{i:02d}.jpg",
            arquivo_url=f"https://cdn.example.com/foto{i:02d}.jpg",
            ordem=i,
            ativa=True,
        )

    with CaptureQueriesContext(connection) as ctx_1:
        resp_1 = auth_ugp.get(detail_url(atividade_1_foto.pk))
    assert resp_1.status_code == status.HTTP_200_OK
    assert len(resp_1.data["fotos"]) == 1

    with CaptureQueriesContext(connection) as ctx_10:
        resp_10 = auth_ugp.get(detail_url(atividade_10_fotos.pk))
    assert resp_10.status_code == status.HTTP_200_OK
    assert len(resp_10.data["fotos"]) == 10

    assert len(ctx_1.captured_queries) == len(ctx_10.captured_queries), (
        f"Esperava número de queries constante, mas obteve "
        f"{len(ctx_1.captured_queries)} (1 foto) vs {len(ctx_10.captured_queries)} (10 fotos)."
    )


# ===========================================================================
# Teste 13 — Escopo territorial: ADT de outro território → 404
# ===========================================================================

@pytest.mark.django_db
def test_escopo_territorial(auth_adt_rn, municipio_ce, usuario_adt_rn):
    """Usuário ADT vinculado ao território RN não deve detalhar atividade do território CE."""
    atividade_ce = ActivityFactory(
        municipio=municipio_ce,
        tecnico_responsavel=usuario_adt_rn,
        status="planejado",
    )

    response = auth_adt_rn.get(detail_url(atividade_ce.pk))
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Teste 14 — Atividade inativa (soft-deleted) → 404
# ===========================================================================

@pytest.mark.django_db
def test_atividade_inativa_404(auth_ugp, municipio_rn):
    """Atividade com ativo=False deve retornar 404 no detalhe, mesmo para UGP."""
    atividade = ActivityFactory(municipio=municipio_rn, ativo=False)

    response = auth_ugp.get(detail_url(atividade.pk))
    assert response.status_code == status.HTTP_404_NOT_FOUND
