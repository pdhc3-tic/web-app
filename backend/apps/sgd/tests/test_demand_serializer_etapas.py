"""Etapas de aprovação e nome do solicitante no DemandSerializer."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgd.tests.factories import ApprovalStepFactory, DemandFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/"


def test_detalhe_traz_as_etapas_na_ordem_de_criacao(
    auth_client_solicitante, demand_rascunho_rn, usuario_ugp, usuario_articulador_rn,
):
    ApprovalStepFactory(
        demanda=demand_rascunho_rn, etapa="pre_autorizacao", acao="aprovado",
        responsavel=usuario_articulador_rn,
    )
    ApprovalStepFactory(
        demanda=demand_rascunho_rn, etapa="autorizacao", acao="aprovado",
        responsavel=usuario_ugp, justificativa="Dentro do limite", excedente_autorizado=True,
    )

    response = auth_client_solicitante.get(f"{URL}{demand_rascunho_rn.pk}/")

    assert response.status_code == 200
    etapas = response.data["etapas"]
    assert [e["etapa"] for e in etapas] == ["pre_autorizacao", "autorizacao"]
    assert etapas[0]["etapa_display"] == "Pré-autorização"
    assert etapas[0]["acao_display"] == "Aprovado"
    assert etapas[0]["responsavel_nome"] == usuario_articulador_rn.nome
    assert etapas[1]["justificativa"] == "Dentro do limite"
    assert etapas[1]["excedente_autorizado"] is True
    assert set(etapas[1]) == {
        "id", "etapa", "etapa_display", "acao", "acao_display", "responsavel_nome",
        "justificativa", "excedente_autorizado", "criado_em",
    }


def test_etapa_sem_responsavel_devolve_nome_nulo(auth_client_solicitante, demand_rascunho_rn):
    ApprovalStepFactory(demanda=demand_rascunho_rn, responsavel=None)

    response = auth_client_solicitante.get(f"{URL}{demand_rascunho_rn.pk}/")

    assert response.data["etapas"][0]["responsavel_nome"] is None


def test_demanda_sem_etapas_devolve_lista_vazia(auth_client_solicitante, demand_rascunho_rn):
    response = auth_client_solicitante.get(f"{URL}{demand_rascunho_rn.pk}/")

    assert response.data["etapas"] == []


def test_solicitante_nome_na_listagem_e_no_detalhe(
    auth_client_articulador_rn, activity_rn, solicitante_rn,
):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")

    lista = auth_client_articulador_rn.get(URL)
    detalhe = auth_client_articulador_rn.get(f"{URL}{demand.pk}/")

    assert lista.data[0]["solicitante_nome"] == solicitante_rn.nome
    assert detalhe.data["solicitante_nome"] == solicitante_rn.nome


def test_listagem_nao_faz_consulta_de_etapas_por_demanda(
    auth_client_solicitante, activity_rn, solicitante_rn,
):
    for demanda in DemandFactory.create_batch(3, activity=activity_rn, solicitante=solicitante_rn):
        ApprovalStepFactory.create_batch(2, demanda=demanda)

    with CaptureQueriesContext(connection) as consultas:
        response = auth_client_solicitante.get(URL)

    assert response.status_code == 200
    assert [len(d["etapas"]) for d in response.data] == [2, 2, 2]
    etapas = [q for q in consultas.captured_queries if 'FROM "sgd_approvalstep"' in q["sql"]]
    assert len(etapas) == 1


def test_resposta_da_decisao_inclui_a_etapa_recem_criada(auth_client_articulador_rn, activity_rn, solicitante_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")

    response = auth_client_articulador_rn.post(f"{URL}{demand.pk}/pre-autorizar/")

    assert response.status_code == 200
    assert [e["etapa"] for e in response.data["etapas"]] == ["pre_autorizacao"]
