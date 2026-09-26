"""
Exportação gerada em segundo plano pelo worker Celery.

O arquivo fica no próprio registro (`conteudo`) em vez de em disco: backend e
worker rodam em containers que não compartilham `MEDIA_ROOT`, e o storage local
de desenvolvimento/CI também não é visível entre eles. O conteúdo é apagado junto
com o registro quando a exportação expira.
"""
from django.conf import settings
from django.db import models


class ExportJob(models.Model):
    class Tipo(models.TextChoices):
        PLANO_TRABALHO = "plano_trabalho", "Plano de Trabalho"
        ATIVIDADES = "atividades", "Atividades"
        UPFS = "upfs", "UPFs"

    class Formato(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "XLSX"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        CONCLUIDA = "concluida", "Concluída"
        ERRO = "erro", "Erro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    formato = models.CharField(max_length=4, choices=Formato.choices, verbose_name="Formato")
    filtros = models.JSONField(default=dict, blank=True, verbose_name="Filtros")
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
        verbose_name="Status",
    )
    progresso = models.PositiveSmallIntegerField(default=0, verbose_name="Progresso (%)")
    erro = models.TextField(blank=True, default="", verbose_name="Erro")
    total_registros = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Total de registros"
    )

    nome_arquivo = models.CharField(max_length=255, blank=True, default="", verbose_name="Nome do arquivo")
    content_type = models.CharField(max_length=100, blank=True, default="", verbose_name="Content-Type")
    conteudo = models.BinaryField(null=True, blank=True, editable=False, verbose_name="Conteúdo")

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exportacoes_sgp",
        verbose_name="Solicitante",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    # Última vez que o job foi para a fila (criação ou `repetir`): é a
    # referência para decidir que um job `pendente` se perdeu no broker.
    enfileirado_em = models.DateTimeField(null=True, blank=True, verbose_name="Enfileirado em")
    iniciado_em = models.DateTimeField(null=True, blank=True, verbose_name="Iniciado em")
    concluido_em = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")
    expira_em = models.DateTimeField(null=True, blank=True, verbose_name="Expira em")

    class Meta:
        verbose_name = "Exportação"
        verbose_name_plural = "Exportações"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progresso__lte=100),
                name="ck_exportjob_progresso_ate_100",
            ),
        ]
        indexes = [
            models.Index(fields=["solicitante", "-criado_em"], name="idx_exportjob_solicitante"),
            models.Index(fields=["expira_em"], name="idx_exportjob_expira_em"),
        ]

    def __str__(self):
        return f"ExportJob #{self.pk} — {self.tipo}/{self.formato} ({self.status})"
