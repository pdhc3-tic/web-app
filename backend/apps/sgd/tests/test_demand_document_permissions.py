import pytest
from rest_framework.exceptions import PermissionDenied

from apps.sgd.services.demand_document import exigir_pode_gerenciar_documento
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def test_solicitante_pode_enviar_suporte_em_rascunho(activity_rn, solicitante_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="rascunho")
    exigir_pode_gerenciar_documento(demand, solicitante_rn, "suporte")


def test_solicitante_nao_pode_enviar_documento_fora_de_rascunho_devolvida(activity_rn, solicitante_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
    with pytest.raises(PermissionDenied):
        exigir_pode_gerenciar_documento(demand, solicitante_rn, "suporte")


def test_outro_usuario_nao_pode_enviar_documento_da_demanda(activity_rn, solicitante_rn, usuario_articulador_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="rascunho")
    with pytest.raises(PermissionDenied):
        exigir_pode_gerenciar_documento(demand, usuario_articulador_rn, "suporte")


def test_fgd_pode_enviar_comprovante_em_atendimento(activity_rn, usuario_fgd):
    demand = DemandFactory(activity=activity_rn, status="em_atendimento")
    exigir_pode_gerenciar_documento(demand, usuario_fgd, "comprovante")


def test_solicitante_nao_pode_enviar_comprovante(activity_rn, solicitante_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="em_atendimento")
    with pytest.raises(PermissionDenied):
        exigir_pode_gerenciar_documento(demand, solicitante_rn, "comprovante")


def test_fgd_nao_pode_enviar_comprovante_antes_do_atendimento(activity_rn, usuario_fgd):
    demand = DemandFactory(activity=activity_rn, status="pre_autorizada")
    with pytest.raises(PermissionDenied):
        exigir_pode_gerenciar_documento(demand, usuario_fgd, "comprovante")
