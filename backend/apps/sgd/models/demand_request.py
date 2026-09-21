from django.db import models

from apps.core.fields import EncryptedCharField


TIPO_CHOICES = [
    ("diaria", "Diárias"),
    ("passagem", "Passagens Aéreas"),
    ("veiculo", "Locação de Veículo"),
    ("grafico", "Material Gráfico"),
    ("alimentacao", "Alimentação"),
    ("equipamento", "Aquisição de Equipamentos"),
]


class DemandRequest(models.Model):
    demanda = models.ForeignKey(
        "sgd.Demand",
        on_delete=models.CASCADE,
        related_name="solicitacoes",
        verbose_name="Demanda",
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")

    rubrica = models.ForeignKey(
        "sgp.BudgetRubrica",
        on_delete=models.PROTECT,
        related_name="solicitacoes_sgd",
        verbose_name="Rubrica",
    )

    campos_json = models.JSONField(default=dict, verbose_name="Campos do formulário")

    # Coluna própria, não uma chave em `campos_json` — nunca fica em texto
    # claro na coluna JSON.
    beneficiario_cpf = EncryptedCharField(
        max_length=14, null=True, blank=True, default=None,
        verbose_name="CPF do beneficiário (criptografado)",
    )

    valor_estimado = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Estimado (R$)",
    )
    valor_autorizado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name="Valor Autorizado (R$)",
    )
    valor_pago = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name="Valor Pago (R$)",
    )

    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Solicitação de Recurso"
        verbose_name_plural = "Solicitações de Recurso"
        ordering = ["demanda", "ordem"]
        indexes = [
            models.Index(fields=["demanda"], name="idx_demandrequest_demanda"),
            models.Index(
                fields=["rubrica", "valor_autorizado"], name="idx_demreq_rubrica_autoriz",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.demanda_id}"
