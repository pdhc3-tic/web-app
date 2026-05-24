from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import signals
from django.dispatch import receiver


class TipoNotificacao(models.TextChoices):
    EMAIL = "email", "E-mail"
    PUSH = "push", "Push"
    WHATSAPP = "whatsapp", "WhatsApp"
    IN_APP = "in_app", "In-App"


class StatusNotificacao(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    ENVIADO = "enviado", "Enviado"
    ENTREGUE = "entregue", "Entregue"
    FALHOU = "falhou", "Falhou"
    CANCELADO = "cancelado", "Cancelado"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    tipo = models.CharField(max_length=20, choices=TipoNotificacao.choices)
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField()
    link = models.URLField(blank=True, default="")
    modulo_origem = models.CharField(max_length=100, blank=True, default="")
    evento = models.CharField(max_length=100, blank=True, default="")
    enviado_em = models.DateTimeField(null=True, blank=True)
    lido_em = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusNotificacao.choices,
        default=StatusNotificacao.PENDENTE,
    )
    tentativas = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-enviado_em"]
        indexes = [
            models.Index(
                fields=["user", "lido_em"],
                name="idx_notif_user_lido_em",
            ),
            models.Index(
                fields=["user", "-enviado_em"],
                name="idx_notif_user_enviado_em",
            ),
        ]
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"[{self.tipo}] {self.titulo} → {self.user}"


class NotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    tipo_evento = models.CharField(max_length=100)
    canal = models.CharField(max_length=20, choices=TipoNotificacao.choices)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tipo_evento", "canal"],
                name="uq_notifpref_user_evento_canal",
            )
        ]
        verbose_name = "Preferência de Notificação"
        verbose_name_plural = "Preferências de Notificação"

    def __str__(self):
        estado = "ativo" if self.ativo else "inativo"
        return f"{self.user} | {self.tipo_evento} via {self.canal} ({estado})"


def _invalidate_unread_cache(user_id):
    """Invalida o cache de contagem de não-lidas do usuário."""
    cache.delete(f"notification_unread_count_{user_id}")


@receiver(signals.post_save, sender=Notification)
def invalidate_unread_count_on_save(sender, instance, **kwargs):
    """Invalida o cache sempre que uma notificação é criada ou atualizada."""
    _invalidate_unread_cache(instance.user_id)
