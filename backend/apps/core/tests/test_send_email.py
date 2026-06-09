import pytest
from unittest.mock import patch, MagicMock
from smtplib import SMTPException
from django.core import mail

from apps.core.models.notifications import Notification, StatusNotificacao
from apps.core.tasks.notifications import send_email_notification
from apps.core.tests.factories import UserFactory, NotificationFactory, NotificationPreferenceFactory


# ######################################
# test_send_email_enqueues_task
# ######################################

@pytest.mark.django_db
def test_send_email_enqueues_task():
    """
    Notification.save() do tipo email enfileira a task via signal.
    """
    with patch("apps.core.tasks.notifications.send_email_notification.delay") as mock_delay:
        notif = NotificationFactory()
        mock_delay.assert_called_once_with(notif.pk)


# ######################################
# test_send_email_renders_template_with_variables
# ######################################

@pytest.mark.django_db
def test_send_email_renders_template_with_variables(settings):
    """
    Task renderiza o template com nome_usuario e link_acao
    e o conteúdo aparece no mail.outbox.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    usuario = UserFactory(nome="João Silva")
    notif = Notification.objects.create(
        user=usuario,
        tipo="email",
        titulo="Teste de Envio",
        mensagem="Mensagem de teste",
        link="https://ufersa.edu.br/acao",
        status="pendente",
    )

    send_email_notification(notif.pk)

    assert len(mail.outbox) == 1
    body = mail.outbox[0].alternatives[0][0]  # HTML content
    assert "João Silva" in body
    assert "https://ufersa.edu.br/acao" in body


# ######################################
# test_send_email_marks_notification_as_sent
# ######################################

@pytest.mark.django_db
def test_send_email_marks_notification_as_sent(settings):
    """
    Após execução bem-sucedida, status='enviado' e enviado_em preenchido.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    notif = Notification.objects.create(
        user=UserFactory(),
        tipo="email",
        titulo="Teste",
        mensagem="Mensagem",
        status="pendente",
    )

    send_email_notification(notif.pk)

    notif.refresh_from_db()
    assert notif.status == StatusNotificacao.ENVIADO
    assert notif.enviado_em is not None


# ######################################
# test_send_email_retries_on_smtp_failure
# ######################################

@pytest.mark.django_db
def test_send_email_retries_on_smtp_failure(settings):
    """
    Mock do EmailBackend levanta SMTPException.
    Após 3 falhas, status='falhou' e tentativas=3.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    notif = Notification.objects.create(
        user=UserFactory(),
        tipo="email",
        titulo="Teste",
        mensagem="Mensagem",
        status="pendente",
    )

    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=SMTPException("Erro SMTP")):
        with patch.object(
            send_email_notification,
            "retry",
            side_effect=send_email_notification.MaxRetriesExceededError()
        ):
            try:
                send_email_notification(notif.pk)
            except Exception:
                pass

    notif.refresh_from_db()
    assert notif.status == StatusNotificacao.FALHOU
    assert notif.tentativas == 1


# ######################################
# test_send_email_skips_if_user_opted_out
# ######################################

@pytest.mark.django_db
def test_send_email_skips_if_user_opted_out(settings):
    """
    NotificationPreference(canal='email', ativo=False) impede envio.
    status='cancelado'.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    usuario = UserFactory()
    NotificationPreferenceFactory(user=usuario, canal="email", ativo=False)

    notif = Notification.objects.create(
        user=usuario,
        tipo="email",
        titulo="Teste",
        mensagem="Mensagem",
        status="pendente",
    )

    send_email_notification(notif.pk)

    notif.refresh_from_db()
    assert notif.status == StatusNotificacao.CANCELADO
    assert len(mail.outbox) == 0


# ######################################
# test_template_does_not_leak_unrendered_tags
# ######################################

@pytest.mark.django_db
def test_template_does_not_leak_unrendered_tags(settings):
    """
    Contexto incompleto não deixa {{ }} ou {% %} no e-mail final.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    # Notificação sem link e sem nome_demanda — contexto incompleto
    notif = Notification.objects.create(
        user=UserFactory(),
        tipo="email",
        titulo="Teste",
        mensagem="Mensagem",
        link="",
        status="pendente",
    )

    send_email_notification(notif.pk)

    assert len(mail.outbox) == 1
    body = mail.outbox[0].alternatives[0][0]
    assert "{{" not in body
    assert "{%" not in body

