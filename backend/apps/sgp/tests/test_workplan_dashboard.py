from datetime import date, timedelta
from decimal import Decimal
from time import monotonic
from unittest.mock import patch

import pytest

from apps.sgp.tasks import check_acao_progress_alert
from apps.sgp.tests.factories import (
    ActivityFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
)


pytestmark = pytest.mark.django_db

PANEL_URL = "/api/v1/sgp/plano-trabalho/painel/"


def create_action_with_progress(meta, numero, municipio, completed, planned=10):
    today = date.today()
    action = WorkPlanAcaoFactory(
        meta=meta,
        numero=numero,
        quantidade_planejada=Decimal(str(planned)),
        data_inicio=today - timedelta(days=10),
        data_fim=today + timedelta(days=10),
    )
    for _ in range(completed):
        ActivityFactory(acao=action, municipio=municipio, status="concluido")
    return action


class TestWorkPlanDashboard:
    def test_returns_indicators_and_summary_per_meta(self, auth_client, municipio):
        meta = WorkPlanMetaFactory(numero=1)
        create_action_with_progress(meta, "1.1", municipio, completed=5)
        create_action_with_progress(meta, "1.2", municipio, completed=3)
        create_action_with_progress(meta, "1.3", municipio, completed=1)

        response = auth_client.get(PANEL_URL)

        assert response.status_code == 200
        assert response.data["metas"][0]["meta"]["id"] == meta.pk
        assert response.data["metas"][0]["resumo"] == {
            "total_acoes": 3,
            "verde": 1,
            "amarelo": 1,
            "vermelho": 1,
        }
        assert [action["semaforo"] for action in response.data["metas"][0]["acoes"]] == [
            "verde", "amarelo", "vermelho"
        ]
        assert response.data["metas"][0]["acoes"][0]["percentual_realizado"] == "50.00"
        assert response.data["metas"][0]["acoes"][0]["progresso_esperado"] == "50.00"

    def test_keeps_summary_separate_for_each_meta(self, auth_client, municipio):
        first_meta = WorkPlanMetaFactory(numero=1)
        second_meta = WorkPlanMetaFactory(numero=2)
        create_action_with_progress(first_meta, "1.1", municipio, completed=5)
        create_action_with_progress(first_meta, "1.2", municipio, completed=1)
        create_action_with_progress(second_meta, "2.1", municipio, completed=3)

        response = auth_client.get(PANEL_URL)

        assert response.status_code == 200
        assert [item["meta"] for item in response.data["metas"]] == [
            {
                "id": first_meta.pk,
                "numero": first_meta.numero,
                "titulo": first_meta.titulo,
            },
            {
                "id": second_meta.pk,
                "numero": second_meta.numero,
                "titulo": second_meta.titulo,
            },
        ]
        assert [item["resumo"] for item in response.data["metas"]] == [
            {"total_acoes": 2, "verde": 1, "amarelo": 0, "vermelho": 1},
            {"total_acoes": 1, "verde": 0, "amarelo": 1, "vermelho": 0},
        ]

    def test_filters_by_meta_territory_and_execution_status(
        self, auth_client, municipio, municipio_ce, territory
    ):
        meta = WorkPlanMetaFactory(numero=1)
        other_meta = WorkPlanMetaFactory(numero=2)
        visible = create_action_with_progress(meta, "1.1", municipio, completed=1)
        create_action_with_progress(other_meta, "2.1", municipio_ce, completed=1)
        completed = create_action_with_progress(meta, "1.2", municipio, completed=10)

        response = auth_client.get(
            f"{PANEL_URL}?meta_id={meta.pk}&territorio_id={territory.pk}"
            "&status_execucao=concluida"
        )

        assert response.status_code == 200
        assert [action["id"] for action in response.data["metas"][0]["acoes"]] == [completed.pk]
        assert visible.pk != completed.pk

    def test_adt_only_sees_actions_with_activities_in_own_territory(
        self, auth_client_adt_rn, municipio_rn, municipio_ce
    ):
        meta = WorkPlanMetaFactory(numero=1)
        own_action = create_action_with_progress(meta, "1.1", municipio_rn, completed=1)
        create_action_with_progress(meta, "1.2", municipio_ce, completed=1)
        WorkPlanAcaoFactory(meta=meta, numero="1.3")

        response = auth_client_adt_rn.get(PANEL_URL)

        assert response.status_code == 200
        assert [action["id"] for action in response.data["metas"][0]["acoes"]] == [own_action.pk]

    def test_adt_progress_counts_only_activities_in_own_territory(
        self, auth_client_adt_rn, municipio_rn, municipio_ce
    ):
        meta = WorkPlanMetaFactory(numero=1)
        action = create_action_with_progress(meta, "1.1", municipio_rn, completed=1)
        ActivityFactory(acao=action, municipio=municipio_ce, status="concluido")

        response = auth_client_adt_rn.get(PANEL_URL)

        assert response.status_code == 200
        assert response.data["metas"][0]["acoes"][0]["quantidade_realizada"] == "1.00"

    def test_rejects_invalid_filter(self, auth_client):
        response = auth_client.get(f"{PANEL_URL}?meta_id=invalida")

        assert response.status_code == 400
        assert "meta_id" in response.data

    def test_returns_one_hundred_actions_under_one_second(self, auth_client, municipio):
        meta = WorkPlanMetaFactory(numero=1)
        for index in range(1, 101):
            create_action_with_progress(
                meta, f"1.{index}", municipio, completed=1
            )

        started_at = monotonic()
        response = auth_client.get(PANEL_URL)
        elapsed = monotonic() - started_at

        assert response.status_code == 200
        assert sum(len(meta["acoes"])
                    for meta in response.data["metas"]
        ) == 100
        assert elapsed < 1


class TestWorkPlanProgressAlerts:
    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_creates_email_notifications_for_ugp_and_super_admin(
        self, mocked_delay, usuario, usuario_super_admin, municipio
    ):
        meta = WorkPlanMetaFactory(numero=1)
        action = create_action_with_progress(meta, "1.1", municipio, completed=1)

        total = check_acao_progress_alert()

        assert total == 2
        assert mocked_delay.call_count == 2
        notifications = usuario.notifications.filter(evento="workplan_action_red")
        assert notifications.count() == 1
        assert str(action.numero) in notifications.first().titulo

    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_does_not_notify_when_no_action_is_red(
        self, mocked_delay, usuario, municipio
    ):
        meta = WorkPlanMetaFactory(numero=1)
        create_action_with_progress(meta, "1.1", municipio, completed=5)

        assert check_acao_progress_alert() == 0
        assert mocked_delay.call_count == 0

    def test_schedule_runs_at_noon(self, settings):
        schedule = settings.CELERY_BEAT_SCHEDULE["check_acao_progress_alert"]

        assert schedule["task"] == "sgp.tasks.check_acao_progress_alert"
        assert schedule["schedule"].hour == {12}
        assert schedule["schedule"].minute == {0}
