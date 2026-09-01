from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import UserProfile
from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.models import Activity, GoogleCalendarSyncEvent
from apps.sgp.tasks import sync_activity_to_google_calendar
from apps.sgp.tests.factories import ActivityFactory


pytestmark = pytest.mark.django_db


def configure_google_calendar(active=True):
    SystemConfig.objects.update_or_create(
        chave="google_calendar_integracao_ativa",
        defaults={
            "valor": str(active),
            "tipo": TipoConfiguracao.BOOLEAN,
            "descricao": "",
        },
    )
    SystemConfig.objects.update_or_create(
        chave="google_calendar_calendario_destino_id",
        defaults={
            "valor": "calendar@example.com",
            "tipo": TipoConfiguracao.STRING,
            "descricao": "",
        },
    )
    SystemConfig.objects.update_or_create(
        chave="google_calendar_lembretes",
        defaults={
            "valor": "[1440, 60]",
            "tipo": TipoConfiguracao.JSON,
            "descricao": "",
        },
    )
    cache.clear()


def mock_google_service():
    service = Mock()
    events = service.events.return_value
    events.insert.return_value.execute.return_value = {"id": "event-123"}
    events.update.return_value.execute.return_value = {"id": "event-456"}
    events.delete.return_value.execute.return_value = {}
    return service


def test_transicao_para_agendada_chama_events_insert_com_payload_correto():
    configure_google_calendar(active=True)
    tecnico = UserFactory(email="tecnico@example.com", nome="Técnico Responsável")
    equipe = UserFactory(email="equipe@example.com", nome="Equipe Adicional")
    activity = ActivityFactory(
        status="agendado",
        tecnico_responsavel=tecnico,
        titulo="Manejo agroecológico",
        tipo_atividade="oficina",
        data_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 8, 0)),
        data_fim=timezone.make_aware(timezone.datetime(2026, 8, 10, 12, 0)),
        latitude="-5.1870000",
        longitude="-37.3440000",
    )
    activity.equipe_adicional.add(equipe)
    service = mock_google_service()

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service):
        sync_activity_to_google_calendar(activity.pk)

    insert = service.events.return_value.insert
    assert insert.called
    kwargs = insert.call_args.kwargs
    assert kwargs["calendarId"] == "calendar@example.com"
    assert kwargs["sendUpdates"] == "all"
    payload = kwargs["body"]
    assert payload["summary"] == "[Oficina] — Manejo agroecológico"
    assert payload["start"]["dateTime"].startswith("2026-08-10T08:00:00")
    assert payload["end"]["dateTime"].startswith("2026-08-10T12:00:00")
    assert "GPS: -5.1870000, -37.3440000" in payload["location"]
    assert "Ação do PT:" in payload["description"]
    assert "Link da atividade no Ecossistema PDHC:" in payload["description"]
    assert payload["attendees"] == [
        {"email": "tecnico@example.com"},
        {"email": "equipe@example.com"},
    ]
    assert payload["reminders"]["overrides"] == [
        {"method": "popup", "minutes": 1440},
        {"method": "popup", "minutes": 60},
    ]
    activity.refresh_from_db()
    assert activity.google_calendar_event_id == "event-123"
    assert activity.google_calendar_sync_status == "ok"
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is True
    assert evento.mensagem_erro == ""


def test_alteracao_em_atividade_agendada_chama_events_update():
    configure_google_calendar(active=True)
    activity = ActivityFactory(
        status="agendado",
        google_calendar_event_id="event-existing",
        data_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 9, 0)),
        data_fim=timezone.make_aware(timezone.datetime(2026, 8, 10, 11, 0)),
    )
    service = mock_google_service()

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service):
        sync_activity_to_google_calendar(activity.pk)

    update = service.events.return_value.update
    assert update.called
    assert update.call_args.kwargs["eventId"] == "event-existing"
    activity.refresh_from_db()
    assert activity.google_calendar_event_id == "event-456"
    assert activity.google_calendar_sync_status == "ok"


def test_transicao_para_cancelada_chama_events_delete():
    configure_google_calendar(active=True)
    activity = ActivityFactory(
        status="cancelada",
        google_calendar_event_id="event-existing",
        justificativa="Cancelamento informado pela equipe.",
    )
    service = mock_google_service()

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service):
        sync_activity_to_google_calendar(activity.pk)

    delete = service.events.return_value.delete
    assert delete.called
    assert delete.call_args.kwargs["eventId"] == "event-existing"
    activity.refresh_from_db()
    assert activity.google_calendar_event_id == ""
    assert activity.google_calendar_sync_status == "ok"


def test_falha_da_api_marca_erro_notifica_sentry_e_super_admin():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super@example.com", nome="Super Admin")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "Google indisponível"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception") as capture_exception, \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    capture_exception.assert_called_once()
    send_email.assert_called_once()
    assert send_email.call_args.args[2] == ["super@example.com"]
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    assert evento.mensagem_erro == "Google indisponível"


def test_multiplas_falhas_mesma_activity_geram_eventos_distintos():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super2@example.com", nome="Super Admin 2")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "Google indisponível"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay"):
        sync_activity_to_google_calendar(activity.pk)
        sync_activity_to_google_calendar(activity.pk)
        sync_activity_to_google_calendar(activity.pk)

    eventos = GoogleCalendarSyncEvent.objects.filter(activity=activity)
    assert eventos.count() == 3
    assert all(e.sucesso is False for e in eventos)


def test_integracao_desativada_nao_enfileira_task():
    configure_google_calendar(active=False)
    role = RoleFactory(slug="ugp", nome="UGP")
    user = UserFactory(email="ugp@example.com", nome="UGP")
    UserProfile.objects.create(user=user, perfil=role)
    activity = ActivityFactory(status="planejado")
    client = APIClient()
    client.force_authenticate(user=user)

    with patch("apps.sgp.views.sync_activity_to_google_calendar.delay") as delay:
        response = client.patch(
            f"/api/v1/sgp/atividades/{activity.pk}/",
            {"status": "agendado"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK, response.data
    delay.assert_not_called()
