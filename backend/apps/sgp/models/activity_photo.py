"""
Model ActivityPhoto — fotos vinculadas a uma atividade do SGP.
Armazenamento no Cloudflare R2 via URL presignada.
"""
from django.conf import settings
from django.db import models


class ActivityPhoto(models.Model):
    activity = models.ForeignKey(
        "sgp.Activity",
        on_delete=models.CASCADE,
        related_name="fotos",
        verbose_name="Atividade",
    )
    arquivo_key = models.CharField(
        max_length=512,
        verbose_name="Key do arquivo (R2)",
    )
    arquivo_url = models.URLField(
        max_length=1024,
        verbose_name="URL pública do arquivo",
    )
    legenda = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Legenda",
    )
    # Preenchido via EXIF (quando disponível) ou timestamp de upload
    data_hora_captura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data/hora de captura",
    )
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name="Latitude",
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name="Longitude",
    )
    # ordem=0 → foto de capa da atividade
    ordem = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="0 = capa da atividade. Usado para drag-and-drop no frontend.",
    )
    content_type = models.CharField(
        max_length=50,
        default="image/jpeg",
        verbose_name="Content-Type",
    )
    tamanho_bytes = models.PositiveBigIntegerField(
        default=0,
        verbose_name="Tamanho em bytes",
    )

    # Soft-delete
    ativa = models.BooleanField(default=True, verbose_name="Ativa")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="fotos_atividade_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Foto da Atividade"
        verbose_name_plural = "Fotos da Atividade"
        ordering = ["ordem", "criado_em"]
        indexes = [
            models.Index(fields=["activity", "ativa"], name="idx_actphoto_activity_ativa"),
            models.Index(fields=["activity", "ordem"], name="idx_actphoto_activity_ordem"),
        ]

    def __str__(self):
        return f"Foto #{self.pk} — {self.activity_id} (ordem {self.ordem})"
