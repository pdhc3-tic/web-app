from datetime import timedelta

import pytest
from django.utils import timezone

from apps.sgd.exceptions import TransicaoInvalida
from apps.sgd.models.demand import Demand
from apps.sgd.services import workflow as workflow_service
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db

TRANSICOES_VALIDAS = [
    ("rascunho", "submetida"),
    ("submetida", "pre_autorizada"),
    ("submetida", "devolvida"),
    ("devolvida", "submetida"),
    ("pre_autorizada", "autorizada"),
    ("pre_autorizada", "recusada"),
    ("autorizada", "em_atendimento"),
    ("em_atendimento", "concluida"),
]


@pytest.mark.parametrize("de,para", TRANSICOES_VALIDAS)
def test_transicao_valida_esta_na_tabela(de, para):
    transicao = workflow_service.buscar_transicao(de, para)
    assert de in transicao.de and transicao.para == para


def test_transicao_fora_da_tabela_rejeitada():
    with pytest.raises(TransicaoInvalida):
        workflow_service.buscar_transicao("rascunho", "autorizada")


def test_transicao_a_partir_de_estado_terminal_rejeitada():
    with pytest.raises(TransicaoInvalida):
        workflow_service.buscar_transicao("concluida", "submetida")


def test_transicoes_permitidas_da_api_deixam_o_cancelamento_de_fora():
    assert workflow_service.destinos_permitidos("submetida") == ["devolvida", "pre_autorizada"]
    assert workflow_service.destinos_permitidos("autorizada") == ["em_atendimento"]
    assert workflow_service.destinos_permitidos("cancelada") == []


def test_executar_transicao_persiste_status_e_data_da_mudanca(activity_rn, usuario_fgd):
    demand = DemandFactory(activity=activity_rn, status="autorizada")
    antiga = timezone.now() - timedelta(days=10)
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=antiga)
    demand.refresh_from_db()

    workflow_service.executar_transicao(demand, "em_atendimento", ator=usuario_fgd)

    demand.refresh_from_db()
    assert demand.status == "em_atendimento"
    assert demand.status_alterado_em > antiga


def test_cancelamento_pelo_sistema_persiste_status_e_data_da_mudanca(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="pre_autorizada")
    antiga = timezone.now() - timedelta(days=10)
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=antiga)
    demand.refresh_from_db()

    workflow_service.cancelar_pelo_sistema([demand], motivo="Atividade cancelada.")

    demand.refresh_from_db()
    assert demand.status == "cancelada"
    assert demand.status_alterado_em > antiga
