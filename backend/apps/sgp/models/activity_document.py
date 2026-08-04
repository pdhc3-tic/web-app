"""
Model ActivityDocument — documentos vinculados a uma atividade do SGP.
Armazenamento no Cloudflare R2. Apenas PDF aceito (máx. 10 MB, máx. 5 docs).
"""
from django.conf import settings
from django.db import models


class ActivityDocument(models.Model):
    TIPO_LISTA_PRESENCA = "lista_presenca"
    TIPO_ATA = "ata"
    TIPO_RELATORIO_PARCIAL = "relatorio_parcial"
    TIPO_DECLARACAO = "declaracao"
    TIPO_CONTRATO = "contrato"
    TIPO_OUTRO = "outro"

    TIPO_CHOICES = [
        (TIPO_LISTA_PRESENCA, "Lista de presença"),
        (TIPO_ATA, "Ata"),
        (TIPO_RELATORIO_PARCIAL, "Relatório parcial"),
        (TIPO_DECLARACAO, "Declaração"),
        (TIPO_CONTRATO, "Contrato"),
        (TIPO_OUTRO, "Outro"),
    ]

    activity = models.ForeignKey(
        "sgp.Activity",
        on_delete=models.CASCADE,
        related_name="documentos",
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
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        verbose_name="Tipo",
    )
    descricao = models.TextField(
        blank=True,
        default="",
        verbose_name="Descrição",
    )
    nome_original = models.CharField(
        max_length=255,
        verbose_name="Nome original do arquivo",
    )
    content_type = models.CharField(
        max_length=100,
        default="application/pdf",
        verbose_name="Content-Type",
    )
    tamanho_bytes = models.PositiveBigIntegerField(
        default=0,
        verbose_name="Tamanho em bytes",
    )
    data_documento = models.DateField(
        verbose_name="Data do documento",
    )

    # Soft-delete
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="documentos_atividade_criados",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Documento da Atividade"
        verbose_name_plural = "Documentos da Atividade"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(
                fields=["activity", "ativo"], name="idx_actdoc_activity_ativo"
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.nome_original}"
