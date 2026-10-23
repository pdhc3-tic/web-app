from django.db import models

from apps.sgd.models.demand_request import TIPO_CHOICES


class DemandTypeRubricaMapping(models.Model):
    """Mapeamento tipo de solicitação -> rubrica (SGD §3, RF05).

    Configuração do sistema mantida pelo Super Admin. Cada tipo tem no máximo
    um mapeamento ativo; a rubrica é atribuída a `DemandRequest` na criação e
    alterações aqui não afetam solicitações já existentes.
    """

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de solicitação")
    rubrica = models.ForeignKey(
        "sgp.BudgetRubrica",
        on_delete=models.PROTECT,
        related_name="mapeamentos_tipo_sgd",
        verbose_name="Rubrica",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mapeamento tipo → rubrica"
        verbose_name_plural = "Mapeamentos tipo → rubrica"
        ordering = ["tipo", "-ativo", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo"], condition=models.Q(ativo=True), name="uniq_tipo_rubrica_ativo",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.rubrica}"
