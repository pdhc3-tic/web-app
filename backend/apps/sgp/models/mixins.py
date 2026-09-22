from django.db import models


class ScaSyncableModel(models.Model):
    device_id = models.CharField(
        max_length=100,
        blank=True, default="",
        verbose_name="Device ID",
        help_text="Identificador do dispositivo de origem (sync SCA).",
    )
    uuid_local = models.UUIDField(
        null=True, blank=True,
        unique=True,
        verbose_name="UUID Local",
        help_text="UUID gerado pelo dispositivo para idempotência no sync SCA.",
    )
    ultima_origem = models.CharField(
        max_length=10,
        choices=[("sca", "SCA"), ("web", "Web")],
        default="web",
        verbose_name="Última Origem",
        help_text="Indica se a última alteração partiu do app SCA ou da plataforma Web.",
    )
    ultimo_sync_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último Sync SCA",
        help_text="Timestamp da última sincronização bem-sucedida via SCA.",
    )

    class Meta:
        abstract = True
