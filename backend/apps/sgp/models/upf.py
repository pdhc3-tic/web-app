from django.conf import settings
from django.db import models

from apps.sgp.constants import (
    AGUA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)


class UPF(models.Model):
    projeto = models.ForeignKey(
        "sgp.Projeto",
        on_delete=models.CASCADE,
        related_name="upfs",
        verbose_name="Projeto",
    )
    comunidade = models.ForeignKey(
        "sgp.Comunidade",
        on_delete=models.PROTECT,
        related_name="upfs",
        null=True,
        blank=True,
        verbose_name="Comunidade",
    )
    titular = models.OneToOneField(
        "sgp.MembroFamilia",
        on_delete=models.PROTECT,
        related_name="upf_titular",
        verbose_name="Titular",
    )

    apelido = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Apelido"
    )

    whatsapp = models.CharField(
        max_length=20, blank=True, default="", verbose_name="WhatsApp"
    )
    celular = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Celular"
    )
    internet = models.BooleanField(
        default=False, verbose_name="Acesso à Internet"
    )
    dispositivo = models.PositiveSmallIntegerField(
        choices=DISPOSITIVO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Dispositivo",
    )

    cep = models.CharField(
        max_length=8, blank=True, default="", verbose_name="CEP",
    )
    logradouro = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Logradouro",
    )
    numero = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Número",
    )
    complemento = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Complemento",
    )
    bairro = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Bairro",
    )

    municipio = models.ForeignKey(
        "core.Municipality",
        on_delete=models.PROTECT,
        related_name="upfs",
        verbose_name="Município",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.PROTECT,
        related_name="upfs",
        verbose_name="Território",
    )

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True, verbose_name="Latitude",
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True, verbose_name="Longitude",
    )

    pct = models.PositiveSmallIntegerField(
        choices=PCT_CHOICES, null=True, blank=True, verbose_name="PCT",
    )
    posse_terra = models.PositiveSmallIntegerField(
        choices=POSSE_TERRA_CHOICES, null=True, blank=True,
        verbose_name="Posse da Terra",
    )
    area_terra_ha = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True, verbose_name="Área da Terra (ha)",
    )
    situacao_moradia = models.PositiveSmallIntegerField(
        choices=SITUACAO_MORADIA_CHOICES, null=True, blank=True,
        verbose_name="Situação da Moradia",
    )
    tipo_moradia = models.PositiveSmallIntegerField(
        choices=TIPO_MORADIA_CHOICES, null=True, blank=True,
        verbose_name="Tipo de Moradia",
    )
    material_construcao = models.PositiveSmallIntegerField(
        choices=MATERIAL_CONSTRUCAO_CHOICES, null=True, blank=True,
        verbose_name="Material de Construção",
    )
    num_comodos = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Número de Cômodos",
    )
    energia = models.PositiveSmallIntegerField(
        choices=ENERGIA_CHOICES, null=True, blank=True, verbose_name="Energia",
    )
    agua = models.PositiveSmallIntegerField(
        choices=AGUA_CHOICES, null=True, blank=True, verbose_name="Água",
    )

    numero_dap = models.CharField(
        max_length=30, blank=True, default="", verbose_name="Número DAP",
    )
    nis = models.CharField(
        max_length=11, blank=True, default="", verbose_name="NIS",
    )

    seguridade_social = models.JSONField(
        default=list, blank=True, verbose_name="Seguridade Social",
    )

    foto_url = models.URLField(
        blank=True, default="", verbose_name="URL da Foto"
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Criado por",
    )

    ativa = models.BooleanField(default=True, verbose_name="Ativa")
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

    class Meta:
        verbose_name = "UPF"
        verbose_name_plural = "UPFs"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["municipio"], name="idx_upf_municipio"),
            models.Index(fields=["territorio"], name="idx_upf_territorio"),
            models.Index(fields=["projeto"], name="idx_upf_projeto"),
            models.Index(fields=["comunidade"], name="idx_upf_comunidade"),
        ]

    def __str__(self):
        return f"{self.titular.nome_completo} - {self.titular.cpf}"
