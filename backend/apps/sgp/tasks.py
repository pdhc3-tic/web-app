import logging

from celery import shared_task

from apps.core.utils import get_config
from apps.sgp.services.google_calendar import (
    build_event_payload,
    delete_event,
    get_google_calendar_service,
    insert_event,
    update_event,
)
from setup.tasks import send_email_notification

try:
    import sentry_sdk
except ImportError:
    class _NullSentry:
        def capture_exception(self, exc):
            return None

    sentry_sdk = _NullSentry()


logger = logging.getLogger(__name__)


@shared_task(name="sgp.tasks.sync_activity_to_google_calendar")
def sync_activity_to_google_calendar(activity_id):
    from apps.sgp.models import Activity

    if not get_config("google_calendar_integracao_ativa", False):
        logger.info(
            "Google Calendar sync ignorado: integração desativada activity_id=%s.",
            activity_id,
        )
        return

    try:
        activity = _get_activity(activity_id)
        event_id = activity.google_calendar_event_id

        if activity.status in {"cancelada", "nao_realizada"} and not event_id:
            _set_sync_success(Activity, activity.pk, "")
            return

        calendar_id = get_config("google_calendar_calendario_destino_id", "")
        if not calendar_id:
            raise ValueError("calendario_destino_id não configurado.")

        service = get_google_calendar_service()

        if activity.status == "agendado":
            reminders = get_config("google_calendar_lembretes", [1440, 60])
            payload = build_event_payload(activity, reminders)
            if event_id:
                event_id = update_event(service, calendar_id, event_id, payload)
            else:
                event_id = insert_event(service, calendar_id, payload)
            _set_sync_success(Activity, activity.pk, event_id)
            return

        if activity.status in {"cancelada", "nao_realizada"}:
            if event_id:
                delete_event(service, calendar_id, event_id)
            _set_sync_success(Activity, activity.pk, "")
            return

        logger.info(
            "Google Calendar sync ignorado: status sem ação activity_id=%s status=%s.",
            activity.pk,
            activity.status,
        )
    except Exception as exc:
        logger.exception(
            "Falha ao sincronizar atividade com Google Calendar activity_id=%s.",
            activity_id,
        )
        sentry_sdk.capture_exception(exc)
        Activity.objects.filter(pk=activity_id).update(
            google_calendar_sync_status="erro",
        )
        _notify_super_admins(activity_id, exc)


def _get_activity(activity_id):
    from apps.sgp.models import Activity

    return (
        Activity.objects.select_related(
            "acao",
            "municipio",
            "comunidade",
            "tecnico_responsavel",
        )
        .prefetch_related("equipe_adicional")
        .get(pk=activity_id)
    )


def _set_sync_success(activity_model, activity_id, event_id):
    activity_model.objects.filter(pk=activity_id).update(
        google_calendar_event_id=event_id,
        google_calendar_sync_status="ok",
    )


def _notify_super_admins(activity_id, exc):
    from apps.core.models import User

    recipients = list(
        User.objects.filter(
            ativo=True,
            profiles__perfil__slug="super-admin",
        )
        .exclude(email="")
        .distinct()
        .values_list("email", flat=True)
    )
    if not recipients:
        return

    send_email_notification.delay(
        "Falha na sincronização com Google Calendar",
        (
            "Ocorreu uma falha ao sincronizar a atividade "
            f"{activity_id} com o Google Calendar. Erro: {exc}"
        ),
        recipients,
    )
