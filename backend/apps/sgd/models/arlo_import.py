from django.conf import settings
from django.db import models


class ArloImport(models.Model):
    """Histórico das exportações e importações trocadas com o Arlo (SGD-RF31/RF32)."""

    class Tipo(models.TextChoices):
        EXPORTACAO = "exportacao", "Exportação"
        IMPORTACAO = "importacao", "Importação"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        CONCLUIDO = "concluido", "Concluído"
        FALHOU = "falhou", "Falhou"

    tipo = models.CharField(max_length=12, choices=Tipo.choices, verbose_name="Tipo")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDENTE,
        db_index=True, verbose_name="Status",
    )
    arquivo_key = models.CharField(max_length=512, verbose_name="Key do arquivo")
    arquivo_url = models.URLField(max_length=1024, verbose_name="URL do arquivo")
    nome_original = models.CharField(max_length=255, blank=True, default="", verbose_name="Nome original do arquivo")
    operado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="operacoes_arlo",
        verbose_name="Operado por",
    )
    operado_em = models.DateTimeField(auto_now_add=True, verbose_name="Operado em")
    ip_origem = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP de origem",
        help_text="IP de quem enviou o arquivo — repassado à auditoria das movimentações feitas pela task.",
    )
    total_registros = models.PositiveIntegerField(default=0, verbose_name="Total de registros")
    registros_ok = models.PositiveIntegerField(default=0, verbose_name="Registros processados com sucesso")
    erros_json = models.JSONField(
        default=list, blank=True, verbose_name="Erros por linha",
        help_text="Lista de {linha, erro, campo?} — linhas com erro não interrompem as válidas.",
    )

    class Meta:
        verbose_name = "Operação Arlo"
        verbose_name_plural = "Operações Arlo"
        ordering = ["-operado_em"]
        indexes = [
            models.Index(fields=["tipo", "-operado_em"], name="idx_arlo_tipo_operado"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.pk} — {self.operado_em:%d/%m/%Y}"
