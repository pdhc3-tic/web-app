"""
Models do módulo SCA — sincronização offline (delta sync).

Endpoints suportados (seção 4 e 9 do SCA_Requisitos):
- POST /api/v1/sca/sync/push
- GET  /api/v1/sca/sync/pull
- GET  /api/v1/sca/sync/forms
- GET  /api/v1/sca/sync/status
- POST /api/v1/sca/auth/refresh
"""

from django.conf import settings
from django.db import models


class SyncDevice(models.Model):
    """Dispositivo de um técnico no app de campo (SCA offline)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sca_devices",
        verbose_name="Usuário",
    )
    device_id = models.CharField(max_length=100, verbose_name="Device ID")
    nome = models.CharField(max_length=255, blank=True, default="", verbose_name="Nome do dispositivo")
    modelo = models.CharField(max_length=100, blank=True, default="", verbose_name="Modelo")
    sistema_operacional = models.CharField(max_length=50, blank=True, default="", verbose_name="Sistema operacional")
    app_versao = models.CharField(max_length=20, blank=True, default="", verbose_name="Versão do app")

    ultimo_push_em = models.DateTimeField(null=True, blank=True, verbose_name="Último push")
    ultimo_pull_em = models.DateTimeField(null=True, blank=True, verbose_name="Último pull")
    ultimo_refresh_em = models.DateTimeField(null=True, blank=True, verbose_name="Último refresh")

    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Dispositivo SCA"
        verbose_name_plural = "Dispositivos SCA"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="uniq_sca_device_user_device",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "ativo"], name="idx_sca_device_user_ativo"),
        ]

    def __str__(self):
        return f"{self.device_id} ({self.user.email})"

    @property
    def ultimo_sync_em(self):
        candidatos = [
            ts for ts in (self.ultimo_push_em, self.ultimo_pull_em) if ts is not None
        ]
        return max(candidatos) if candidatos else None


class SyncEvent(models.Model):
    """Registro de cada sincronização bem-sucedida (push/pull/refresh)."""

    class Tipo(models.TextChoices):
        PUSH = "push", "Push"
        PULL = "pull", "Pull"
        REFRESH = "refresh", "Refresh"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sca_sync_events",
        verbose_name="Usuário",
    )
    device = models.ForeignKey(
        "sca.SyncDevice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_events",
        verbose_name="Dispositivo",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Tipo")
    since = models.DateTimeField(null=True, blank=True, verbose_name="Since (pull)")
    contagem = models.PositiveIntegerField(default=0, verbose_name="Registros processados")
    recebido_em = models.DateTimeField(auto_now_add=True, verbose_name="Recebido em")

    class Meta:
        verbose_name = "Evento de Sincronização"
        verbose_name_plural = "Eventos de Sincronização"
        ordering = ["-recebido_em"]
        indexes = [
            models.Index(fields=["user", "-recebido_em"], name="idx_sca_event_user_rec"),
        ]

    def __str__(self):
        return f"{self.tipo} {self.user_id} em {self.recebido_em:%Y-%m-%d %H:%M}"


class ConflictLog(models.Model):
    """Registro de conflito de sincronização (seção 4 do SCA_Requisitos)."""

    class Estrategia(models.TextChoices):
        LAST_WRITE_WINS = "last_write_wins", "Last-write-wins"
        DUPLICATE_REJEITADO = "duplicate_rejeitado", "Duplicata rejeitada"
        EXCLUSAO_PREVALECE = "exclusao_prevalece", "Exclusão do servidor prevalece"
        MERGE_AUTOMATICO = "merge_automatico", "Merge automático"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sca_conflicts",
        verbose_name="Usuário",
    )
    device = models.ForeignKey(
        "sca.SyncDevice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conflicts",
        verbose_name="Dispositivo",
    )
    entidade = models.CharField(max_length=50, verbose_name="Entidade")
    uuid_local = models.UUIDField(verbose_name="UUID local")
    campo = models.CharField(max_length=255, verbose_name="Campo em conflito")
    valor_local = models.JSONField(default=dict, verbose_name="Valor local (offline)")
    valor_servidor = models.JSONField(default=dict, verbose_name="Valor no servidor")
    estrategia = models.CharField(
        max_length=30,
        choices=Estrategia.choices,
        default=Estrategia.LAST_WRITE_WINS,
        verbose_name="Estratégia aplicada",
    )
    campo_sensivel = models.BooleanField(default=False, verbose_name="Campo sensível")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Log de Conflito"
        verbose_name_plural = "Logs de Conflito"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["user", "-criado_em"], name="idx_sca_conflict_user"),
            models.Index(fields=["uuid_local"], name="idx_sca_conflict_uuid"),
        ]

    def __str__(self):
        return f"Conflito {self.entidade}/{self.uuid_local} — {self.campo}"
