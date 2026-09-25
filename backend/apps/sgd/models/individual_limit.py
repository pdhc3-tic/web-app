from django.conf import settings
from django.db import models


class DemandIndividualLimit(models.Model):
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="limites_individuais_sgd",
        verbose_name="Solicitante",
    )
    rubrica = models.ForeignKey(
        "sgp.BudgetRubrica",
        on_delete=models.PROTECT,
        related_name="limites_individuais",
        verbose_name="Rubrica",
    )
    valor_limite = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Limite (R$)",
    )
    valor_comprometido = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Comprometido (R$)",
    )
    valor_executado = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Executado (R$)",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="limites_individuais_sgd_criados",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Limite Individual de Demanda"
        verbose_name_plural = "Limites Individuais de Demanda"
        ordering = ["solicitante", "rubrica"]
        constraints = [
            models.UniqueConstraint(
                fields=["solicitante", "rubrica"],
                name="unique_demandindividuallimit_solicitante_rubrica",
            ),
        ]

    def __str__(self):
        return f"{self.solicitante} · {self.rubrica} — limite R$ {self.valor_limite}"

    @property
    def saldo_disponivel(self):
        return self.valor_limite - self.valor_comprometido - self.valor_executado
