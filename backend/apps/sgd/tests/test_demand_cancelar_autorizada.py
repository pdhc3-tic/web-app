"""Cancelamento de demanda autorizada: perfis, justificativa, saldo e timeline."""
import threading
from decimal import Decimal

import pytest
from django.db import connection
from rest_framework.exceptions import ValidationError

from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.demand import Demand
from apps.sgd.services import demand as demand_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def demanda_autorizada(demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand.status = "autorizada"
    demand.save(update_fields=["status"])
    return demand


def _url(demand):
    return f"/api/v1/sgd/demandas/{demand.pk}/cancelar/"


def test_ugp_cancela_autorizada_com_justificativa(auth_client_ugp, demanda_autorizada):
    response = auth_client_ugp.post(_url(demanda_autorizada), {"justificativa": "Evento suspenso"}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "cancelada"
    evento = response.data["etapas"][-1]
    assert evento["acao"] == "cancelado"
    assert evento["justificativa"] == "Evento suspenso"


def test_cancelar_autorizada_sem_justificativa_retorna_400(auth_client_ugp, demanda_autorizada):
    response = auth_client_ugp.post(_url(demanda_autorizada), {"justificativa": "  "}, format="json")

    assert response.status_code == 400
    demanda_autorizada.refresh_from_db()
    assert demanda_autorizada.status == "autorizada"


def test_super_admin_cancela_autorizada(auth_client_super_admin, demanda_autorizada, limite_individual_rn):
    response = auth_client_super_admin.post(_url(demanda_autorizada), {"justificativa": "Erro de cadastro"}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "cancelada"
    assert response.data["etapas"][-1]["acao"] == "cancelado"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")


@pytest.mark.django_db(transaction=True)
def test_cancelamentos_simultaneos_registram_um_so_evento(demanda_autorizada, usuario_ugp, usuario_super_admin):
    # As duas instâncias são lidas antes, ambas em `autorizada`: as duas threads
    # passam pela checagem de status, qualquer que seja a ordem em que rodem.
    instancias = [Demand.objects.get(pk=demanda_autorizada.pk) for _ in range(2)]
    barreira = threading.Barrier(2)
    resultados = []

    def cancelar(demand, usuario):
        try:
            barreira.wait()
            demand_service.cancelar_demanda(demand, usuario=usuario, motivo="Evento suspenso")
            resultados.append("cancelada")
        except ValidationError:
            resultados.append("recusada")
        finally:
            connection.close()

    threads = [
        threading.Thread(target=cancelar, args=(instancia, usuario))
        for instancia, usuario in zip(instancias, [usuario_ugp, usuario_super_admin])
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert sorted(resultados) == ["cancelada", "recusada"]
    assert ApprovalStep.objects.filter(demanda=demanda_autorizada, acao="cancelado").count() == 1


@pytest.mark.parametrize("cliente", ["auth_client_solicitante", "auth_client_fgd"])
def test_perfil_nao_autorizado_nao_cancela_autorizada(request, cliente, demanda_autorizada):
    response = request.getfixturevalue(cliente).post(
        _url(demanda_autorizada), {"justificativa": "x"}, format="json",
    )

    assert response.status_code == 403
    demanda_autorizada.refresh_from_db()
    assert demanda_autorizada.status == "autorizada"


def test_cancelar_autorizada_libera_limite_e_pool_uma_unica_vez(
    auth_client_ugp, demanda_autorizada, limite_individual_rn, allocation_territorial_rn,
):
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido > Decimal("0")

    auth_client_ugp.post(_url(demanda_autorizada), {"justificativa": "Cancelada"}, format="json")
    segunda = auth_client_ugp.post(_url(demanda_autorizada), {"justificativa": "Cancelada"}, format="json")

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")
    assert segunda.status_code == 400


def test_evento_de_cancelamento_aparece_na_timeline(auth_client_ugp, demanda_autorizada):
    auth_client_ugp.post(_url(demanda_autorizada), {"justificativa": "Cancelada"}, format="json")

    detalhe = auth_client_ugp.get(f"/api/v1/sgd/demandas/{demanda_autorizada.pk}/")
    assert detalhe.data["etapas"][-1]["acao"] == "cancelado"
    assert ApprovalStep.objects.filter(demanda=demanda_autorizada, acao="cancelado").count() == 1


def test_solicitante_continua_cancelando_submetida_com_motivo_legado(
    auth_client_solicitante, demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)

    response = auth_client_solicitante.post(_url(demand), {"motivo": "Desisti"}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "cancelada"
