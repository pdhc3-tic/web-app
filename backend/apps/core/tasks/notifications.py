import logging
from smtplib import SMTPException

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models.notifications import Notification, NotificationPreference, StatusNotificacao

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    name="core.tasks.send_email_notification",
)
def send_email_notification(self, notification_id: int) -> None:
    """
    Envia e-mail para o usuário referente à notificação informada.

    Fluxo:
      1. Busca a Notification pelo ID — aborta se não encontrar.
      2. Verifica preferência do usuário — cancela se opted-out.
      3. Renderiza o template HTML com o contexto da notificação.
      4. Envia via SMTP configurado no settings.
      5. Em sucesso: marca status='enviado' e preenche enviado_em.
      6. Em falha SMTP: incrementa tentativas e agenda retry com backoff.
      7. Após 3 falhas: marca status='falhou'.
    """
    try:
        notification = Notification.objects.select_related("user").get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.error("send_email_notification: Notification %s não encontrada.", notification_id)
        return

    # Verifica preferência — se opted-out, cancela
    opted_out = NotificationPreference.objects.filter(
        user=notification.user,
        canal="email",
        ativo=False,
    ).exists()

    if opted_out:
        notification.status = StatusNotificacao.CANCELADO
        notification.save(update_fields=["status"])
        logger.info(
            "send_email_notification: usuário %s opted-out de e-mail. Notificação %s cancelada.",
            notification.user_id,
            notification_id,
        )
        return

    # Contexto para o template
    context = {
        "nome_usuario": getattr(notification.user, "nome", "") or "",
        "nome_demanda": notification.titulo or "",
        "data_prazo": "",
        "link_acao": notification.link or "",
        "mensagem": notification.mensagem or "",
        "titulo": notification.titulo or "",
    }

    # Renderiza o template
    html_content = render_to_string("emails/base.html", context)
    text_content = notification.mensagem or ""

    # Envia o e-mail
    try:
        email = EmailMultiAlternatives(
            subject=notification.titulo,
            body=text_content,
            to=[notification.user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        notification.status = StatusNotificacao.ENVIADO
        notification.enviado_em = timezone.now()
        notification.save(update_fields=["status", "enviado_em"])

        logger.info(
            "send_email_notification: e-mail enviado com sucesso para %s (notification_id=%s).",
            notification.user.email,
            notification_id,
        )

    except SMTPException as exc:
        notification.tentativas += 1
        notification.save(update_fields=["tentativas"])

        logger.warning(
            "send_email_notification: falha SMTP (tentativa %s/3) para notification_id=%s: %s",
            notification.tentativas,
            notification_id,
            exc,
        )

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            notification.status = StatusNotificacao.FALHOU
            notification.save(update_fields=["status"])
            logger.error(
                "send_email_notification: máximo de tentativas atingido para notification_id=%s.",
                notification_id,
            )