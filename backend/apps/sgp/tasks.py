import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.utils import get_config
from apps.sgp.services.google_calendar import (
    build_event_payload,
    delete_event,
    get_google_calendar_service,
    insert_event,
    update_event,
)
from setup.tasks import send_email_notification
from apps.core.models.notifications import Notification, TipoNotificacao
from apps.core.models.user import User
from apps.sgp.services.workplan_dashboard import dashboard_actions, enrich_dashboard_action
from apps.sgp.services.budget import alocacoes_em_vermelho
from apps.sgp.cache import set_power_bi_snapshot
from apps.sgp.services.workplan_export import workplan_export_rows


try:
    import sentry_sdk
except ImportError:
    class _NullSentry:
        def capture_exception(self, exc):
            return None

    sentry_sdk = _NullSentry()


logger = logging.getLogger(__name__)


def refresh_power_bi_snapshot():
    """Materializa o dataset de BI no Redis para manter a leitura da API barata."""
    snapshot = {
        "atualizado_em": timezone.now().isoformat(),
        "resultados": workplan_export_rows(),
    }
    set_power_bi_snapshot(snapshot)
    return snapshot


@shared_task(name="sgp.tasks.export_to_power_bi")
def export_to_power_bi() -> dict:
    snapshot = refresh_power_bi_snapshot()
    logger.info(
        "Snapshot Power BI atualizado: linhas=%s atualizado_em=%s.",
        len(snapshot["resultados"]),
        snapshot["atualizado_em"],
    )
    return snapshot


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
        from apps.sgp.models import GoogleCalendarSyncEvent

        with transaction.atomic():
            Activity.objects.filter(pk=activity_id).update(
                google_calendar_sync_status="erro",
            )
            GoogleCalendarSyncEvent.objects.create(
                activity_id=activity_id,
                sucesso=False,
                mensagem_erro=str(exc),
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
    from apps.sgp.models import GoogleCalendarSyncEvent

    with transaction.atomic():
        activity_model.objects.filter(pk=activity_id).update(
            google_calendar_event_id=event_id,
            google_calendar_sync_status="ok",
        )
        GoogleCalendarSyncEvent.objects.create(activity_id=activity_id, sucesso=True)


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

@shared_task(name="sgp.tasks.check_acao_progress_alert")
def check_acao_progress_alert() -> int:
    """Notifica UGP e Super Admin sobre Ações em vermelho no semáforo.

    A execução diária cria uma notificação por destinatário e Ação. O signal de
    Notification enfileira o envio pelo serviço central de e-mail.
    """
    try:
        recipients = User.objects.filter(
            ativo=True,
            profiles__perfil__slug__in=["ugp", "super-admin"],
        ).distinct()
        if not recipients.exists():
            return 0

        red_actions = []
        for action in dashboard_actions():
            action = enrich_dashboard_action(action)
            if action.dashboard_semaforo == "vermelho":
                red_actions.append(action)
        notifications_sent = 0
        panel_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/sgp/plano-trabalho"

        for action in red_actions:
            message = (
                f"A Ação {action.numero} ({action.descricao}) está em vermelho: "
                f"{action.dashboard_percentual_realizado}% realizado para "
                f"{action.dashboard_progresso_esperado}% esperado."
            )
            for recipient in recipients:
                Notification.objects.create(
                    user=recipient,
                    tipo=TipoNotificacao.EMAIL,
                    titulo=f"Alerta de progresso: Ação {action.numero}",
                    mensagem=message,
                    link=panel_url,
                    modulo_origem="sgp",
                    evento="workplan_action_red",
                )
                notifications_sent += 1

        return notifications_sent
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao verificar alertas do Plano de Trabalho.")
        raise


@shared_task(name="sgp.tasks.check_budget_threshold_alert")
def check_budget_threshold_alert() -> int:
    """Notifica UGP e Super Admin sobre alocações em vermelho no semáforo do
    orçamento (§5.3.3: comprometido ≥ 80% do alocado), em qualquer nível.

    Mesmo padrão de `check_acao_progress_alert`: execução diária, uma notificação
    por destinatário e alocação vermelha.
    """
    try:
        recipients = User.objects.filter(
            ativo=True,
            profiles__perfil__slug__in=["ugp", "super-admin"],
        ).distinct()
        if not recipients.exists():
            return 0

        notifications_sent = 0
        panel_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/sgp/orcamento"

        for allocation in alocacoes_em_vermelho():
            message = (
                f"A alocação de {allocation.meta.titulo} / {allocation.rubrica.nome} "
                f"({allocation.get_nivel_display()}) está em vermelho: "
                f"R$ {allocation.valor_comprometido} comprometido de "
                f"R$ {allocation.valor_alocado} aprovado."
            )
            for recipient in recipients:
                Notification.objects.create(
                    user=recipient,
                    tipo=TipoNotificacao.EMAIL,
                    titulo=(
                        f"Alerta de orçamento: {allocation.meta.titulo} / "
                        f"{allocation.rubrica.nome}"
                    ),
                    mensagem=message,
                    link=panel_url,
                    modulo_origem="sgp",
                    evento="budget_allocation_red",
                )
                notifications_sent += 1

        return notifications_sent
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao verificar alertas de orçamento.")
        raise
