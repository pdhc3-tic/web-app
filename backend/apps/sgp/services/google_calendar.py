import json

from django.conf import settings
from django.utils import timezone


GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarConfigError(Exception):
    pass


def get_google_calendar_service():
    credentials = _get_service_account_credentials()
    delegated_user = getattr(settings, "GOOGLE_CALENDAR_DELEGATED_USER", "")
    if delegated_user:
        credentials = credentials.with_subject(delegated_user)

    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _get_service_account_credentials():
    from google.oauth2 import service_account

    service_account_info = getattr(settings, "GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO", "")
    service_account_file = getattr(settings, "GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE", "")

    if service_account_info:
        try:
            info = json.loads(service_account_info)
        except json.JSONDecodeError as exc:
            raise GoogleCalendarConfigError(
                "GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO não contém JSON válido."
            ) from exc
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=GOOGLE_CALENDAR_SCOPES,
        )

    if service_account_file:
        return service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=GOOGLE_CALENDAR_SCOPES,
        )

    raise GoogleCalendarConfigError(
        "Configure GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO ou "
        "GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE."
    )


def build_event_payload(activity, reminders):
    attendees = _attendees(activity)
    payload = {
        "summary": f"[{activity.get_tipo_atividade_display()}] — {activity.titulo}",
        "start": {
            "dateTime": _google_datetime(activity.data_inicio),
            "timeZone": settings.TIME_ZONE,
        },
        "end": {
            "dateTime": _google_datetime(activity.data_fim),
            "timeZone": settings.TIME_ZONE,
        },
        "location": _location(activity),
        "description": _description(activity),
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": minutes}
                for minutes in reminders
            ],
        },
    }
    if attendees:
        payload["attendees"] = attendees
    return payload


def insert_event(service, calendar_id, payload):
    response = service.events().insert(
        calendarId=calendar_id,
        body=payload,
        sendUpdates="all",
    ).execute()
    return response["id"]


def update_event(service, calendar_id, event_id, payload):
    response = service.events().update(
        calendarId=calendar_id,
        eventId=event_id,
        body=payload,
        sendUpdates="all",
    ).execute()
    return response.get("id", event_id)


def delete_event(service, calendar_id, event_id):
    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendUpdates="all",
    ).execute()


def _google_datetime(value):
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return timezone.localtime(value).isoformat()


def _attendees(activity):
    emails = []
    if activity.tecnico_responsavel.email:
        emails.append(activity.tecnico_responsavel.email)
    emails.extend(
        activity.equipe_adicional.exclude(email="").values_list("email", flat=True)
    )
    return [{"email": email} for email in dict.fromkeys(emails)]


def _location(activity):
    parts = [activity.municipio.nome]
    if activity.comunidade_id:
        parts.append(activity.comunidade.nome)
    if activity.latitude is not None and activity.longitude is not None:
        parts.append(f"GPS: {activity.latitude}, {activity.longitude}")
    return " - ".join(parts)


def _description(activity):
    activity_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/sgp/atividades/{activity.pk}"
    return "\n".join(
        [
            f"Tipo: {activity.get_tipo_atividade_display()}",
            f"Ação do PT: {activity.acao.numero} - {activity.acao.descricao}",
            f"Âmbito: {activity.get_ambito_display()}",
            f"Link da atividade no Ecossistema PDHC: {activity_url}",
        ]
    )
