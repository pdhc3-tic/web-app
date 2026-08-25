from django.conf import settings
from django.db import models

from apps.sgp.constants import (
    COR_RACA_CHOICES,
    ESCOLARIDADE_CHOICES,
    GENERO_CHOICES,
    PARENTESCO_CHOICES,
)


class MembroFamilia(models.Model):
    upf = models.ForeignKey(
        "sgp.UPF",
        on_delete=models.CASCADE,
        related_name="membros",
        null=True,
        blank=True,
        verbose_name="UPF",
    )

    nome_completo = models.CharField(
        max_length=255, verbose_name="Nome Completo"
    )
    data_nasc = models.DateField(
        null=True, blank=True, verbose_name="Data de Nascimento"
    )
    genero = models.PositiveSmallIntegerField(
        choices=GENERO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Gênero",
    )
    cor_raca = models.PositiveSmallIntegerField(
        choices=COR_RACA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Cor/Raça",
    )

    cpf = models.CharField(
        max_length=11,
        blank=True,
        default="",
        verbose_name="CPF",
    )
    rg = models.CharField(
        max_length=20, blank=True, default="", verbose_name="RG"
    )
    nis = models.CharField(
        max_length=11,
        blank=True,
        default="",
        verbose_name="NIS",
    )
    caf = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="CAF",
    )

    parentesco = models.CharField(
        max_length=20,
        choices=PARENTESCO_CHOICES,
        verbose_name="Parentesco",
    )

    escola = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Escola",
    )
    seguridade_social = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Seguridade Social",
    )

    saude = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Condições de Saúde",
    )

    escolaridade = models.PositiveSmallIntegerField(
        choices=ESCOLARIDADE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Escolaridade",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )

    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    # ── Sync SCA (compatibilidade com dispositivos offline) ──────────────────
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
        verbose_name = "Membro da Família"
        verbose_name_plural = "Membros da Família"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["upf"],
                condition=models.Q(parentesco="titular"),
                name="unique_titular_por_upf",
            ),
        ]
        indexes = [
            models.Index(fields=["upf"], name="idx_membro_upf"),
        ]

    def __str__(self):
        return f"{self.nome_completo} ({self.get_parentesco_display()})"
