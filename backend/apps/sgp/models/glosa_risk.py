from django.conf import settings
from django.db import models
from django.db.models import Q


class GlosaRisk(models.Model):
    """Risco de glosa. `demanda_id`, `demand_request_id` e `arlo_import_id` são referências fracas
    ao SGD, sem FK, no mesmo padrão de `BudgetTransaction.demanda_id`."""

    ENTIDADE_DEMANDA = "demanda"

    class Tipo(models.TextChoices):
        PAGO_ACIMA_AUTORIZADO = "pago_acima_autorizado", "Pago acima do autorizado"
        DEMANDA_SEM_EVIDENCIA = "demanda_sem_evidencia", "Demanda executada sem evidência"

    class Severidade(models.TextChoices):
        ALTA = "alta", "Alta"
        MEDIA = "media", "Média"
        BAIXA = "baixa", "Baixa"

    tipo_situacao = models.CharField(max_length=30, choices=Tipo.choices, verbose_name="Situação")
    severidade = models.CharField(max_length=5, choices=Severidade.choices, verbose_name="Severidade")
    entidade = models.CharField(max_length=30, verbose_name="Entidade de origem")
    entidade_id = models.CharField(max_length=64, verbose_name="ID da entidade de origem")
    activity = models.ForeignKey(
        "sgp.Activity", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="riscos_de_glosa", verbose_name="Atividade",
    )
    demanda_id = models.CharField(
        max_length=64, db_index=True, verbose_name="ID da Demanda",
        help_text="Referência fraca a uma Demand do SGD (apps.sgd).",
    )
    demand_request_id = models.CharField(
        max_length=64, blank=True, default="", verbose_name="ID da Solicitação",
        help_text="Referência fraca ao DemandRequest que recebeu o pagamento.",
    )
    arlo_import_id = models.CharField(
        max_length=64, blank=True, default="", verbose_name="ID da importação Arlo",
    )
    valor_autorizado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Valor autorizado (R$)",
    )
    valor_pago = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Valor pago (R$)",
    )
    valor_exposto = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor exposto (R$)")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="glosas_risco_registradas",
        verbose_name="Registrado por",
    )
    detectado_em = models.DateTimeField(auto_now_add=True, verbose_name="Detectado em")
    resolvido_em = models.DateTimeField(null=True, blank=True, verbose_name="Resolvido em")
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="glosas_risco_resolvidas",
        verbose_name="Resolvido por",
    )

    class Meta:
        verbose_name = "Risco de Glosa"
        verbose_name_plural = "Riscos de Glosa"
        ordering = ["-detectado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["demand_request_id", "arlo_import_id"],
                condition=Q(tipo_situacao="pago_acima_autorizado"),
                name="uniq_glosarisk_solicitacao_import",
            ),
            models.UniqueConstraint(
                fields=["entidade", "entidade_id"],
                condition=Q(tipo_situacao="demanda_sem_evidencia"),
                name="uniq_glosarisk_sem_evidencia_por_entidade",
            ),
        ]

    def __str__(self):
        return f"Glosa demanda {self.demanda_id} ({self.tipo_situacao}): R$ {self.valor_exposto}"
