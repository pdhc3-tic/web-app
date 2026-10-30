from django.db import models
from django.db.models import Q

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

    # Estado da reserva no limite individual, gravado sob o lock do limite.
    # `valor_executado` preenchido encerra a reserva: `valor_reservado` fica
    # como registro do que foi convertido em executado.
    valor_reservado = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Reservado (R$)",
    )
    valor_executado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Valor Executado (R$)",
    )
    # Parte de `valor_reservado` coberta por remanejamento emergencial, fora do
    # limite individual: não volta ao limite na liberação nem na execução.
    valor_excedente = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Excedente Autorizado (R$)",
    )

    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Solicitação de Recurso"
        verbose_name_plural = "Solicitações de Recurso"
        ordering = ["demanda", "ordem"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_reservado__gte=0), name="ck_demandrequest_valor_reservado_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_executado__isnull=True) | Q(valor_executado__gte=0),
                name="ck_demandrequest_valor_executado_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_excedente__gte=0) & Q(valor_excedente__lte=models.F("valor_reservado")),
                name="ck_demandrequest_excedente_dentro_da_reserva",
            ),
        ]
        indexes = [
            models.Index(fields=["demanda"], name="idx_demandrequest_demanda"),
            models.Index(
                fields=["rubrica", "valor_autorizado"], name="idx_demreq_rubrica_autoriz",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.demanda_id}"

    @property
    def reserva_ativa(self) -> bool:
        return self.valor_reservado > 0 and self.valor_executado is None

    @property
    def valor_no_limite(self):
        """Parte da reserva comprometida no limite individual do solicitante."""
        return self.valor_reservado - self.valor_excedente


RESERVA_ATIVA = Q(valor_reservado__gt=0, valor_executado__isnull=True)
