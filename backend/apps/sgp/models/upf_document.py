from django.conf import settings
from django.db import models


class UPFDocument(models.Model):
    TIPO_DAP_CAF = "dap_caf"
    TIPO_CONTRATO = "contrato"
    TIPO_LAUDO = "laudo"
    TIPO_IDENTIDADE = "identidade"
    TIPO_OUTRO = "outro"

    TIPO_CHOICES = [
        (TIPO_DAP_CAF, "DAP/CAF"),
        (TIPO_CONTRATO, "Contrato"),
        (TIPO_LAUDO, "Laudo"),
        (TIPO_IDENTIDADE, "Identidade"),
        (TIPO_OUTRO, "Outro"),
    ]

    upf = models.ForeignKey(
        "sgp.UPF",
        on_delete=models.CASCADE,
        related_name="documentos",
        verbose_name="UPF",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name="Tipo",
    )
    descricao = models.TextField(
        blank=True,
        default="",
        verbose_name="Descrição",
    )
    arquivo_key = models.CharField(
        max_length=512,
        verbose_name="Key do Arquivo",
    )
    nome_original = models.CharField(
        max_length=255,
        verbose_name="Nome Original",
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name="Content-Type",
    )
    tamanho_bytes = models.PositiveBigIntegerField(
        verbose_name="Tamanho em Bytes",
    )
    data_documento = models.DateField(
        verbose_name="Data do Documento",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_upf_criados",
        verbose_name="Criado por",
    )

    class Meta:
        verbose_name = "Documento da UPF"
        verbose_name_plural = "Documentos da UPF"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["upf", "-criado_em"], name="idx_upfdoc_upf_criado"),
            models.Index(fields=["arquivo_key"], name="idx_upfdoc_arquivo_key"),
        ]

    def __str__(self):
        return f"{self.upf_id} - {self.nome_original}"
