from django.conf import settings
from django.db import models
from django.db.models import ProtectedError, Q

from .workplan import WorkPlanMeta


class BudgetRubrica(models.Model):
    """Catálogo estável das rubricas orçamentárias (§5.3.1)."""

    nome = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(unique=True, max_length=50, verbose_name="Slug")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")

    class Meta:
        verbose_name = "Rubrica Orçamentária"
        verbose_name_plural = "Rubricas Orçamentárias"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class BudgetAllocation(models.Model):
    """A distribuição de uma Meta/Rubrica entre os três níveis (§5.5).

    `valor_comprometido` e `valor_executado` são materializados, não
    properties — atualizados exclusivamente por BudgetTransaction dentro de
    transação atômica (decisão de projeto: evita o N+1 que
    WorkPlanAcao.quantidade_realizada causa no painel do PT, ver R4 em
    SPRINT_SGP_REFATORACAO.md).
    """

    class Nivel(models.TextChoices):
        NACIONAL = "nacional", "Nacional"
        ESTADUAL = "estadual", "Estadual"
        TERRITORIAL = "territorial", "Territorial"

    meta = models.ForeignKey(
        WorkPlanMeta,
        on_delete=models.CASCADE,
        related_name="alocacoes_orcamento",
        verbose_name="Meta",
    )
    rubrica = models.ForeignKey(
        BudgetRubrica,
        on_delete=models.PROTECT,
        related_name="alocacoes",
        verbose_name="Rubrica",
    )
    nivel = models.CharField(
        max_length=20, choices=Nivel.choices, verbose_name="Nível",
    )
    estado = models.ForeignKey(
        "core.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="alocacoes_orcamento",
        verbose_name="Estado",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="alocacoes_orcamento",
        verbose_name="Território",
    )
    valor_alocado = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Valor Alocado (R$)",
    )
    valor_comprometido = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Valor Comprometido (R$)",
    )
    valor_executado = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Valor Executado (R$)",
    )
    reserva_ugp = models.BooleanField(
        default=False,
        verbose_name="Reserva Própria da UGP",
        help_text="Só em nível nacional. Uma reserva própria da UGP nunca recebe alocações-filhas.",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em",
    )

    class Meta:
        verbose_name = "Alocação Orçamentária"
        verbose_name_plural = "Alocações Orçamentárias"
        ordering = ["meta", "rubrica", "nivel"]
        constraints = [
            models.UniqueConstraint(
                fields=["meta", "rubrica", "nivel", "estado", "territorio"],
                name="unique_budget_allocation_combinacao",
                # sem isso dois NULLs em estado/territorio (nacional/estadual) não colidem no Postgres.
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                # literais, não Nivel.* — Meta não enxerga o namespace de BudgetAllocation.
                condition=(
                    Q(nivel="nacional", estado__isnull=True, territorio__isnull=True)
                    | Q(nivel="estadual", estado__isnull=False, territorio__isnull=True)
                    | Q(nivel="territorial", territorio__isnull=False)
                ),
                name="ck_budget_allocation_nivel_consistente",
            ),
            models.CheckConstraint(
                condition=Q(reserva_ugp=False) | Q(nivel="nacional"),
                name="ck_budget_allocation_reserva_ugp_so_nacional",
            ),
        ]
        indexes = [
            models.Index(fields=["meta", "rubrica"], name="idx_budgetalloc_meta_rubrica"),
            models.Index(fields=["nivel", "territorio"], name="idx_budgetalloc_nivel_territ"),
        ]

    def __str__(self):
        return f"{self.meta} · {self.rubrica} · {self.get_nivel_display()}"


class BudgetTransaction(models.Model):
    """Trilha de auditoria imutável de movimentos sobre uma alocação (§5.5).

    Mesmo padrão de imutabilidade de apps.core.models.audit_log.AuditLog:
    save() bloqueia UPDATE, delete() é bloqueado — aqui com ProtectedError,
    por pedido explícito da issue (#219), não ValueError como o AuditLog.
    """

    class Tipo(models.TextChoices):
        RESERVA = "reserva", "Reserva"
        LIBERACAO = "liberacao", "Liberação"
        EXECUCAO = "execucao", "Execução"
        REMANEJAMENTO = "remanejamento", "Remanejamento"

    allocation = models.ForeignKey(
        BudgetAllocation,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Alocação",
    )
    tipo = models.CharField(
        max_length=20, choices=Tipo.choices, verbose_name="Tipo",
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Valor (R$)",
    )
    demanda_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="ID da Demanda",
        help_text="Referência fraca ao SGD, que ainda não existe.",
    )
    justificativa = models.TextField(
        blank=True, default="", verbose_name="Justificativa",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em",
    )

    class Meta:
        verbose_name = "Transação Orçamentária"
        verbose_name_plural = "Transações Orçamentárias"
        ordering = ["-criado_em"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError(
                "BudgetTransaction é imutável: registros existentes não podem ser alterados."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtectedError(
            "BudgetTransaction é imutável: registros não podem ser removidos.",
            [self],
        )

    def __str__(self):
        return f"[{self.tipo}] {self.allocation} — R$ {self.valor}"
