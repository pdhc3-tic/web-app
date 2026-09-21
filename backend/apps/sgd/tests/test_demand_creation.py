from datetime import datetime

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.services import demand as demand_service
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db


def test_criar_demanda_com_activity_existente_planejado(activity_rn, solicitante_rn):
    demand = demand_service.criar_demanda(
        titulo="Diárias para oficina", activity=activity_rn,
        justificativa="", solicitante=solicitante_rn,
    )
    assert demand.status == "rascunho"
    assert demand.activity_id == activity_rn.pk
    assert demand.despesa_posterior is False


def test_criar_activity_inline(solicitante_rn, municipio_rn):
    from apps.sgp.tests.factories import WorkPlanAcaoFactory

    acao = WorkPlanAcaoFactory()
    data_prevista = timezone.make_aware(datetime(2026, 8, 1, 9, 0))
    activity = demand_service.criar_activity_inline(
        titulo="Seminário Regional", tipo_atividade="seminario", acao=acao,
        municipio=municipio_rn, data_prevista=data_prevista, usuario=solicitante_rn,
    )
    assert activity.status == "planejado"
    assert activity.tecnico_responsavel_id == solicitante_rn.pk


def test_criar_demanda_bloqueada_para_activity_cancelada(solicitante_rn, municipio_rn):
    activity = ActivityFactory(municipio=municipio_rn, status="cancelada")
    with pytest.raises(DRFValidationError):
        demand_service.criar_demanda(
            titulo="Diárias", activity=activity, justificativa="", solicitante=solicitante_rn,
        )


def test_criar_demanda_activity_em_andamento_marca_despesa_posterior(solicitante_rn, municipio_rn):
    activity = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    demand = demand_service.criar_demanda(
        titulo="Diárias", activity=activity, justificativa="Gasto identificado após início.",
        solicitante=solicitante_rn,
    )
    assert demand.despesa_posterior is True


def test_criar_demanda_activity_em_andamento_sem_justificativa_bloqueia(solicitante_rn, municipio_rn):
    activity = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    with pytest.raises(DRFValidationError):
        demand_service.criar_demanda(
            titulo="Diárias", activity=activity, justificativa="", solicitante=solicitante_rn,
        )


def test_editar_demanda_em_rascunho_permitido(demand_rascunho_rn):
    demand = demand_service.atualizar_demanda(demand_rascunho_rn, titulo="Novo título")
    assert demand.titulo == "Novo título"


def test_editar_demanda_autorizada_bloqueado(demand_rascunho_rn):
    demand_rascunho_rn.status = "autorizada"
    demand_rascunho_rn.save(update_fields=["status"])
    with pytest.raises(DRFValidationError):
        demand_service.atualizar_demanda(demand_rascunho_rn, titulo="Outro título")


def test_serializer_rejeita_alteracao_de_activity_id():
    from apps.sgd.serializers.demand import DemandUpdateSerializer

    entrada = DemandUpdateSerializer(data={"titulo": "Novo", "activity_id": 999}, partial=True)
    assert not entrada.is_valid()
    assert "activity_id" in entrada.errors


def test_serializer_aceita_update_sem_activity_id():
    from apps.sgd.serializers.demand import DemandUpdateSerializer

    entrada = DemandUpdateSerializer(data={"titulo": "Novo título"}, partial=True)
    assert entrada.is_valid(), entrada.errors
