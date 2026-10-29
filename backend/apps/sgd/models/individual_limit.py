from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.utils import formatar_brl


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
            models.CheckConstraint(
                condition=Q(valor_comprometido__gte=0), name="ck_demandindividuallimit_comprometido_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_executado__gte=0), name="ck_demandindividuallimit_executado_nao_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.solicitante} · {self.rubrica} — limite R$ {self.valor_limite}"

    @property
    def saldo_disponivel(self):
        return self.valor_limite - self.valor_comprometido - self.valor_executado

    def erro_de_reducao(self, novo_valor) -> str | None:
        """Depois de um excedente o limite já pode estar abaixo do comprometido:
        só a redução é barrada, o aumento ajuda. Confiável só com a linha travada."""
        minimo = self.valor_comprometido + self.valor_executado
        if novo_valor < minimo and novo_valor < self.valor_limite:
            return f"Não pode ser reduzido abaixo do já comprometido e executado: {formatar_brl(minimo)}."
        return None
