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
from apps.sgp.services.google_calendar import GoogleCalendarConfigError
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


def test_falha_de_credencial_marca_erro_notifica_sentry_e_super_admin_sem_chamar_api():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super-credencial@example.com", nome="Super Admin")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")

    with patch(
        "apps.sgp.tasks.get_google_calendar_service",
        side_effect=GoogleCalendarConfigError("Credenciais ausentes ou inválidas."),
    ) as get_service, \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception") as capture_exception, \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    assert get_service.called
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    capture_exception.assert_called_once()
    send_email.assert_called_once()
    assert send_email.call_args.args[2] == ["super-credencial@example.com"]
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    assert "Credenciais ausentes ou inválidas." in evento.mensagem_erro


def test_timeout_da_api_marca_erro_e_notifica_super_admin():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super-timeout@example.com", nome="Super Admin")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = TimeoutError(
        "Tempo de conexão excedido."
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception") as capture_exception, \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    capture_exception.assert_called_once()
    send_email.assert_called_once()
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    assert "Tempo de conexão excedido." in evento.mensagem_erro


def test_falha_em_events_update_marca_erro():
    configure_google_calendar(active=True)
    activity = ActivityFactory(
        status="agendado",
        google_calendar_event_id="event-existing",
    )
    service = mock_google_service()
    service.events.return_value.update.return_value.execute.side_effect = RuntimeError(
        "Falha ao atualizar evento"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay"):
        sync_activity_to_google_calendar(activity.pk)

    assert service.events.return_value.update.called
    assert not service.events.return_value.insert.called
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    assert evento.mensagem_erro == "Falha ao atualizar evento"


def test_evento_ja_deletado_no_google_falha_em_events_delete_marca_erro():
    configure_google_calendar(active=True)
    activity = ActivityFactory(
        status="cancelada",
        google_calendar_event_id="event-existing",
        justificativa="Cancelamento informado pela equipe.",
    )
    service = mock_google_service()
    service.events.return_value.delete.return_value.execute.side_effect = Exception(
        "Not Found: eventId event-existing"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay"):
        sync_activity_to_google_calendar(activity.pk)

    assert service.events.return_value.delete.called
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    # Não há tratamento especial para "evento não encontrado" — cai no
    # catch-all e o event_id permanece como estava, pois _set_sync_success
    # nunca é alcançado.
    assert activity.google_calendar_event_id == "event-existing"
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    assert "Not Found" in evento.mensagem_erro


def test_activity_cancelada_sem_event_id_nao_chama_api_e_marca_sucesso():
    configure_google_calendar(active=True)
    activity = ActivityFactory(status="cancelada")
    service = mock_google_service()

    with patch(
        "apps.sgp.tasks.get_google_calendar_service", return_value=service
    ) as get_service:
        sync_activity_to_google_calendar(activity.pk)

    # Atividade cancelada que nunca teve evento sincronizado: nada a
    # apagar, então a API do Google nem chega a ser consultada.
    assert get_service.called is False
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "ok"
    assert activity.google_calendar_event_id == ""
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is True


def test_integracao_desativada_apos_enfileiramento_mas_antes_da_execucao_e_noop():
    configure_google_calendar(active=True)
    activity = ActivityFactory(status="agendado")
    # Simula a integração sendo desativada depois que a atividade foi
    # marcada para sincronizar, mas antes da task rodar de fato.
    configure_google_calendar(active=False)

    with patch("apps.sgp.tasks.get_google_calendar_service") as get_service:
        sync_activity_to_google_calendar(activity.pk)

    assert get_service.called is False
    assert GoogleCalendarSyncEvent.objects.filter(activity=activity).count() == 0
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "ok"
    assert activity.google_calendar_event_id == ""


def test_falha_ao_buscar_activity_cai_no_except_generico_e_notifica():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super-notfound@example.com", nome="Super Admin")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")

    with patch(
        "apps.sgp.tasks._get_activity", side_effect=Activity.DoesNotExist
    ), patch("apps.sgp.tasks.sentry_sdk.capture_exception") as capture_exception, \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    capture_exception.assert_called_once()
    send_email.assert_called_once()
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False


def test_sem_super_admins_falha_nao_envia_email():
    configure_google_calendar(active=True)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "Google indisponível"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.sucesso is False
    send_email.assert_not_called()


def test_super_admin_inativo_ou_sem_email_excluido_da_notificacao():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    ativo_valido = UserFactory(
        email="super-valido@example.com", nome="Super Válido", ativo=True
    )
    UserProfile.objects.create(user=ativo_valido, perfil=role)
    inativo = UserFactory(
        email="super-inativo@example.com", nome="Super Inativo", ativo=False
    )
    UserProfile.objects.create(user=inativo, perfil=role)
    sem_email = UserFactory(email="", nome="Super Sem Email", ativo=True)
    UserProfile.objects.create(user=sem_email, perfil=role)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "Google indisponível"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    send_email.assert_called_once()
    assert send_email.call_args.args[2] == ["super-valido@example.com"]


def test_calendario_destino_id_ausente_gera_valueerror_e_marca_erro():
    configure_google_calendar(active=True)
    SystemConfig.objects.filter(
        chave="google_calendar_calendario_destino_id"
    ).update(valor="")
    cache.clear()
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    super_admin = UserFactory(email="super-config@example.com", nome="Super Admin")
    UserProfile.objects.create(user=super_admin, perfil=role)
    activity = ActivityFactory(status="agendado")

    with patch("apps.sgp.tasks.get_google_calendar_service") as get_service, \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay"):
        sync_activity_to_google_calendar(activity.pk)

    assert get_service.called is False
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "erro"
    evento = GoogleCalendarSyncEvent.objects.get(activity=activity)
    assert evento.mensagem_erro == "calendario_destino_id não configurado."


def test_falha_ao_enfileirar_task_nao_impede_resposta_http_e_marca_pendente():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="ugp", nome="UGP")
    user = UserFactory(email="ugp-enqueue@example.com", nome="UGP")
    UserProfile.objects.create(user=user, perfil=role)
    activity = ActivityFactory(status="planejado")
    client = APIClient()
    client.force_authenticate(user=user)

    with patch(
        "apps.sgp.views.sync_activity_to_google_calendar.delay",
        side_effect=RuntimeError("fila indisponível"),
    ) as delay:
        response = client.patch(
            f"/api/v1/sgp/atividades/{activity.pk}/",
            {"status": "agendado"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK, response.data
    assert delay.called
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "pendente"


def test_edicao_de_campo_nao_monitorado_em_atividade_agendada_nao_reenfileira():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="ugp", nome="UGP")
    user = UserFactory(email="ugp-titulo@example.com", nome="UGP")
    UserProfile.objects.create(user=user, perfil=role)
    activity = ActivityFactory(status="agendado", titulo="Título original")
    client = APIClient()
    client.force_authenticate(user=user)

    with patch("apps.sgp.views.sync_activity_to_google_calendar.delay") as delay:
        response = client.patch(
            f"/api/v1/sgp/atividades/{activity.pk}/",
            {"titulo": "Título revisado"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK, response.data
    delay.assert_not_called()
    activity.refresh_from_db()
    assert activity.titulo == "Título revisado"
    assert activity.google_calendar_sync_status == "ok"


def test_edicao_de_equipe_adicional_em_atividade_agendada_reenfileira():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="ugp", nome="UGP")
    user = UserFactory(email="ugp-equipe@example.com", nome="UGP")
    UserProfile.objects.create(user=user, perfil=role)
    novo_membro = UserFactory(email="novo-membro@example.com", nome="Novo Membro")
    activity = ActivityFactory(status="agendado")
    client = APIClient()
    client.force_authenticate(user=user)

    with patch("apps.sgp.views.sync_activity_to_google_calendar.delay") as delay:
        response = client.patch(
            f"/api/v1/sgp/atividades/{activity.pk}/",
            {"equipe_adicional": [novo_membro.pk]},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK, response.data
    assert delay.called
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "pendente"


def test_transicao_para_status_neutro_nao_aciona_sync():
    configure_google_calendar(active=True)
    activity = ActivityFactory(status="em_andamento")
    service = mock_google_service()

    with patch(
        "apps.sgp.tasks.get_google_calendar_service", return_value=service
    ) as get_service:
        sync_activity_to_google_calendar(activity.pk)

    # Status fora de {agendado, cancelada, nao_realizada}: a task só loga
    # "ignorado" e não chama nenhum verbo da API do Google.
    assert get_service.called
    assert service.events.called is False
    activity.refresh_from_db()
    assert activity.google_calendar_sync_status == "ok"
    assert GoogleCalendarSyncEvent.objects.filter(activity=activity).count() == 0


def test_multiplos_super_admins_validos_recebem_notificacao():
    configure_google_calendar(active=True)
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    admin_1 = UserFactory(email="super-um@example.com", nome="Super Um")
    UserProfile.objects.create(user=admin_1, perfil=role)
    admin_2 = UserFactory(email="super-dois@example.com", nome="Super Dois")
    UserProfile.objects.create(user=admin_2, perfil=role)
    activity = ActivityFactory(status="agendado")
    service = mock_google_service()
    service.events.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "Google indisponível"
    )

    with patch("apps.sgp.tasks.get_google_calendar_service", return_value=service), \
        patch("apps.sgp.tasks.sentry_sdk.capture_exception"), \
        patch("apps.sgp.tasks.send_email_notification.delay") as send_email:
        sync_activity_to_google_calendar(activity.pk)

    send_email.assert_called_once()
    recipients = send_email.call_args.args[2]
    assert set(recipients) == {"super-um@example.com", "super-dois@example.com"}
