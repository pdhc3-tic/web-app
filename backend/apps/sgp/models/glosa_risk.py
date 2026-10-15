from django.conf import settings
from django.db import models


class GlosaRisk(models.Model):
    """Risco de glosa: valor pago pelo Arlo acima do autorizado (SGD-BE-4).

    O excedente não é executado nos limites — fica só registrado aqui para o
    relatório de risco. `demanda_id`/`arlo_import_id` são referências fracas
    ao SGD, sem FK, no mesmo padrão de BudgetTransaction.demanda_id.
    """

    demanda_id = models.CharField(
        max_length=64, db_index=True, verbose_name="ID da Demanda",
        help_text="Referência fraca a uma Demand do SGD (apps.sgd).",
    )
    demand_request_id = models.CharField(
        max_length=64, verbose_name="ID da Solicitação",
        help_text="Referência fraca ao DemandRequest que recebeu o pagamento.",
    )
    arlo_import_id = models.CharField(
        max_length=64, blank=True, default="", verbose_name="ID da importação Arlo",
    )
    valor_autorizado = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor autorizado (R$)")
    valor_pago = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor pago (R$)")
    excedente = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Excedente (R$)")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="glosas_risco_registradas",
        verbose_name="Registrado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Risco de Glosa"
        verbose_name_plural = "Riscos de Glosa"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["demand_request_id", "arlo_import_id"],
                name="uniq_glosarisk_solicitacao_import",
            ),
        ]

    def __str__(self):
        return f"Glosa demanda {self.demanda_id}: +R$ {self.excedente}"
