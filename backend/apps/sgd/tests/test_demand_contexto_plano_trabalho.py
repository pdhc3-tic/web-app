"""Cadeia do Plano de Trabalho no contexto da demanda (SGD-RF02) e valor
executado da Ação ao concluir a demanda (SGP §5.5)."""
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgd.services import balance as balance_service
from apps.sgd.services.approval import concluir
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.models import WorkPlanAcao

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/"


def test_contexto_traz_submeta_e_indicador(auth_client_solicitante, demand_rascunho_rn):
    acao = demand_rascunho_rn.activity.acao

    response = auth_client_solicitante.get(f"{URL}{demand_rascunho_rn.pk}/")

    contexto = response.data["contexto"]
    assert contexto["acao_numero"] == acao.numero
    assert contexto["submeta_numero"] == acao.submeta.numero
    assert contexto["submeta_titulo"] == acao.submeta.titulo
    assert contexto["meta_numero"] == acao.meta.numero
    assert contexto["indicador_codigo"] == acao.indicador.codigo
    assert contexto["indicador_nome"] == acao.indicador.nome
    assert contexto["indicador_unidade_medida"] == acao.indicador.unidade_medida


def test_listagem_traz_submeta_e_indicador_no_join(
    auth_client_solicitante, activity_rn, solicitante_rn
):
    """A cadeia vem no select_related da consulta principal: nenhuma consulta
    própria a Submeta ou Indicador, qualquer que seja o número de demandas."""
    DemandFactory.create_batch(3, activity=activity_rn, solicitante=solicitante_rn)

    with CaptureQueriesContext(connection) as consultas:
        response = auth_client_solicitante.get(URL)

    assert len(response.data["results"]) == 3
    avulsas = [
        q["sql"] for q in consultas.captured_queries
        if q["sql"].lstrip().startswith(('SELECT "sgp_workplansubmeta"', 'SELECT "sgp_indicator"'))
    ]
    assert avulsas == []


def test_concluir_atualiza_valor_executado_da_acao(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.valor_autorizado = demand_request_rn.valor_estimado
    demand_request_rn.save(update_fields=["valor_autorizado"])
    demand.status = "em_atendimento"
    demand.save(update_fields=["status"])

    concluir(
        demand, responsavel=solicitante_rn,
        valores_pagos={demand_request_rn.pk: Decimal("800.00")},
    )

    acao = WorkPlanAcao.objects.get(pk=demand.activity.acao_id)
    assert acao.valor_executado == Decimal("800.00")
