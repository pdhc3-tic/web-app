from unittest.mock import patch

import pytest

from apps.core.models.notifications import Notification
from apps.sgd.services import balance as balance_service
from apps.sgd.tasks import notificar_demandas_atividade_adiada

pytestmark = pytest.mark.django_db


def test_activity_adiada_agenda_task_de_notificacao(django_capture_on_commit_callbacks, activity_rn):
    with patch("apps.sgd.tasks.notificar_demandas_atividade_adiada.delay") as mocked_delay:
        with django_capture_on_commit_callbacks(execute=True):
            activity_rn.status = "adiada"
            activity_rn.save(update_fields=["status"])

    mocked_delay.assert_called_once_with(activity_rn.pk)


def test_activity_adiada_nao_reagenda_em_saves_subsequentes(django_capture_on_commit_callbacks, activity_rn):
    with patch("apps.sgd.tasks.notificar_demandas_atividade_adiada.delay") as mocked_delay:
        with django_capture_on_commit_callbacks(execute=True):
            activity_rn.status = "adiada"
            activity_rn.save(update_fields=["status"])

        with django_capture_on_commit_callbacks(execute=True):
            activity_rn.descricao_narrativa = "Detalhe atualizado."
            activity_rn.save(update_fields=["descricao_narrativa"])

    mocked_delay.assert_called_once_with(activity_rn.pk)


def test_task_mantem_demanda_e_saldo_e_notifica(
    activity_rn, solicitante_rn, demand_request_rn, allocation_territorial_rn, limite_individual_rn, usuario_articulador_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    activity_rn.status = "adiada"
    activity_rn.save(update_fields=["status"])

    notificar_demandas_atividade_adiada(activity_rn.pk)

    demand.refresh_from_db()
    assert demand.status == "submetida"

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == demand_request_rn.valor_estimado

    assert Notification.objects.filter(
        evento="demand_atividade_adiada", user=usuario_articulador_rn,
    ).exists()


def test_task_nao_notifica_se_activity_nao_esta_mais_adiada(activity_rn, demand_request_rn):
    demand = demand_request_rn.demanda
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    activity_rn.status = "planejado"
    activity_rn.save(update_fields=["status"])

    notificar_demandas_atividade_adiada(activity_rn.pk)

    assert not Notification.objects.filter(evento="demand_atividade_adiada").exists()
