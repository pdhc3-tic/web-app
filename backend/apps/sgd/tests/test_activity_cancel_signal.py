import re
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models.notifications import Notification
from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgd.services import balance as balance_service
from apps.sgd.tasks import cancelar_demandas_da_atividade
from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory

pytestmark = pytest.mark.django_db


def test_activity_cancelada_agenda_task_de_cancelamento(django_capture_on_commit_callbacks, activity_rn):
    """O signal só agenda a task (via transaction.on_commit) — quem cancela
    de fato é apps.sgd.tasks.cancelar_demandas_da_atividade, rodando fora da
    transação da request (ver o motivo no próprio signal)."""
    with patch("apps.sgd.tasks.cancelar_demandas_da_atividade.delay") as mocked_delay:
        with django_capture_on_commit_callbacks(execute=True):
            activity_rn.status = "cancelada"
            activity_rn.justificativa = "Cancelada por decisão da equipe."
            activity_rn.save(update_fields=["status", "justificativa"])

    mocked_delay.assert_called_once_with(activity_rn.pk)


def test_task_cancela_demandas_nao_atendidas_e_libera_saldo(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada por decisão da equipe."
    activity_rn.save(update_fields=["status", "justificativa"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "cancelada"

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == 0
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == 0

    assert Notification.objects.filter(
        evento="demand_cancelada_automatico", user=demand.solicitante,
    ).exists()
    assert Notification.objects.filter(
        evento="demand_cancelada_automatico", user=usuario_articulador_rn,
    ).exists()


def test_task_trava_os_limites_antes_das_alocacoes_e_cancela_as_demandas_por_ultimo(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn,
    rubrica_diarias, territory_rn,
):
    """Dois solicitantes com reserva na mesma alocação: a primeira trava de limite já pega
    os dois, antes de qualquer alocação, e as Demand só mudam depois de todo o saldo
    (ordem de lock de backend/docs/orcamento.md)."""
    vizinho = UserFactory(profiles=[(RoleFactory(slug="adt-acr"), territory_rn)])
    DemandIndividualLimitFactory(solicitante=vizinho, rubrica=rubrica_diarias, valor_limite=5_000)
    da_vizinha = DemandRequestFactory(
        demanda=DemandFactory(activity=activity_rn, solicitante=vizinho, status="submetida"),
        tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("100"),
    )
    for solicitacao, usuario in ((demand_request_rn, solicitante_rn), (da_vizinha, vizinho)):
        balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=usuario)
    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada por decisão da equipe."
    activity_rn.save(update_fields=["status", "justificativa"])

    with CaptureQueriesContext(connection) as consultas:
        assert cancelar_demandas_da_atividade(activity_rn.pk) == 2

    sqls = [q["sql"] for q in consultas]
    travas_de_limite = [i for i, sql in enumerate(sqls) if "FOR UPDATE" in sql and '"sgd_demandindividuallimit"' in sql]
    travas_de_alocacao = [i for i, sql in enumerate(sqls) if "FOR UPDATE" in sql and '"sgp_budgetallocation"' in sql]
    cancelamentos = [i for i, sql in enumerate(sqls) if sql.startswith('UPDATE "sgd_demand" ')]
    primeira_trava_de_limite = sqls[travas_de_limite[0]]
    solicitantes = re.search(r'"solicitante_id" IN \(([^)]*)\)', primeira_trava_de_limite).group(1)
    assert {int(pk) for pk in solicitantes.split(",")} == {solicitante_rn.pk, vizinho.pk}
    assert travas_de_limite[0] < travas_de_alocacao[0]
    assert len(cancelamentos) == 2
    assert min(cancelamentos) > max(travas_de_limite + travas_de_alocacao)
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, allocation_territorial_rn.valor_comprometido) == (0, 0)


def test_task_nao_cancela_demanda_em_atendimento(activity_rn):
    """RF10: "não atendida" exclui quem já está sendo atendida pela FGD —
    só Rascunho/Submetida/Devolvida/Pré-autorizada/Autorizada são
    canceladas automaticamente."""
    demand = DemandFactory(activity=activity_rn, status="em_atendimento")

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada."
    activity_rn.save(update_fields=["status", "justificativa"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "em_atendimento"


def test_task_nao_afeta_demanda_ja_concluida(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="concluida")

    activity_rn.status = "cancelada"
    activity_rn.justificativa = "Cancelada."
    activity_rn.save(update_fields=["status", "justificativa"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "concluida"


def test_task_ignora_activity_que_mudou_de_status_de_novo(activity_rn, demand_request_rn):
    """Entre o commit que agendou a task e ela rodar, a Activity pode ter
    voltado pra outro status (ex.: reativada) — a task não deve cancelar
    nada nesse caso."""
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    activity_rn.status = "planejado"
    activity_rn.save(update_fields=["status"])

    cancelar_demandas_da_atividade(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "submetida"
