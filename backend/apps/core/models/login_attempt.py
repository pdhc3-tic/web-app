from django.db import models
from django.conf import settings


class LoginAttempt(models.Model):
    class MotivFalha(models.TextChoices):
        INVALID_CREDENTIALS = "INVALID_CREDENTIALS", "Credenciais inválidas"
        INACTIVE_USER = "INACTIVE_USER", "Usuário inativo"
        RATE_LIMITED = "RATE_LIMITED", "Limite de tentativas atingido"
        INVALID_FORMAT = "INVALID_FORMAT", "Formato inválido"

    email = models.EmailField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    sucesso = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    motivo_falha = models.CharField(
        max_length=30,
        choices=MotivFalha.choices,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Tentativa de Login"
        verbose_name_plural = "Tentativas de Login"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.email} — {'sucesso' if self.sucesso else self.motivo_falha} — {self.timestamp}"