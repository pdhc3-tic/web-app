from django.conf import settings
from django.db import models


TIPO_CHOICES = [
    ("suporte", "Documento de suporte"),
    ("ata", "Ata"),
    ("comprovante", "Comprovante"),
    ("cotacao", "Cotação"),
]


class DemandDocument(models.Model):
    demanda = models.ForeignKey(
        "sgd.Demand",
        on_delete=models.CASCADE,
        related_name="documentos",
        verbose_name="Demanda",
    )
    arquivo_key = models.CharField(max_length=512, verbose_name="Key do arquivo (R2)")
    arquivo_url = models.URLField(max_length=1024, verbose_name="URL pública do arquivo")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    descricao = models.TextField(blank=True, default="", verbose_name="Descrição")
    nome_original = models.CharField(max_length=255, verbose_name="Nome original do arquivo")
    content_type = models.CharField(
        max_length=100, default="application/pdf", verbose_name="Content-Type",
    )
    tamanho_bytes = models.PositiveBigIntegerField(default=0, verbose_name="Tamanho em bytes")

    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="documentos_demanda_enviados",
        verbose_name="Enviado por",
    )
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em")

    class Meta:
        verbose_name = "Documento da Demanda"
        verbose_name_plural = "Documentos da Demanda"
        ordering = ["-enviado_em"]
        indexes = [
            models.Index(fields=["demanda", "ativo"], name="idx_demanddoc_demanda_ativo"),
            models.Index(fields=["demanda", "tipo", "ativo"], name="idx_demanddoc_demanda_tipo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.nome_original}"
