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
        AJUSTE = "ajuste", "Ajuste"

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
        help_text="Referência fraca a uma Demand do SGD (apps.sgd) — sem FK de propósito, o motor não importa apps.sgd.",
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


class BudgetIncreaseRequest(models.Model):
    """Solicitação de Recurso Extra (SGP §6.6): o usuário pede aumento do próprio
    limite individual em uma rubrica. Fluxo próprio, distinto do da demanda."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        SUBMETIDA = "submetida", "Submetida"
        DEVOLVIDA = "devolvida", "Devolvida"
        COM_PARECER = "com_parecer", "Com parecer"
        APROVADA = "aprovada", "Aprovada"
        APROVADA_PARCIALMENTE = "aprovada_parcialmente", "Aprovada parcialmente"
        RECUSADA = "recusada", "Recusada"

    # Aprovada, aprovada parcialmente e recusada são terminais.
    TRANSICOES = {
        Status.RASCUNHO: {Status.SUBMETIDA},
        Status.SUBMETIDA: {Status.COM_PARECER, Status.DEVOLVIDA},
        Status.DEVOLVIDA: {Status.SUBMETIDA},
        Status.COM_PARECER: {Status.APROVADA, Status.APROVADA_PARCIALMENTE, Status.RECUSADA},
        Status.APROVADA: set(),
        Status.APROVADA_PARCIALMENTE: set(),
        Status.RECUSADA: set(),
    }
    EDITAVEIS = {Status.RASCUNHO, Status.DEVOLVIDA}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="pedidos_recurso_extra", verbose_name="Solicitante",
    )
    rubrica = models.ForeignKey(
        BudgetRubrica, on_delete=models.PROTECT,
        related_name="pedidos_recurso_extra", verbose_name="Rubrica",
    )
    valor_solicitado = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor solicitado (R$)")
    valor_aprovado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Valor aprovado (R$)",
    )
    periodo_aplicacao = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Período de aplicação",
    )
    activity = models.ForeignKey(
        "sgp.Activity", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos_recurso_extra", verbose_name="Atividade que motivou o pedido",
    )
    demanda_id = models.CharField(
        max_length=64, null=True, blank=True, default=None, verbose_name="ID da Demanda",
        help_text="Referência fraca à Demand bloqueada (apps.sgd) — sem FK, no mesmo padrão de BudgetTransaction.demanda_id.",
    )
    justificativa = models.TextField(verbose_name="Justificativa")
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.RASCUNHO, db_index=True, verbose_name="Status",
    )
    parecer_articulador = models.TextField(blank=True, default="", verbose_name="Parecer do Articulador")
    parecer_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pareceres_recurso_extra", verbose_name="Parecer por",
    )
    justificativa_decisao = models.TextField(blank=True, default="", verbose_name="Justificativa da decisão")
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="decisoes_recurso_extra", verbose_name="Decidido por",
    )
    decidido_em = models.DateTimeField(null=True, blank=True, verbose_name="Decidido em")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Solicitação de Recurso Extra"
        verbose_name_plural = "Solicitações de Recurso Extra"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status", "-criado_em"], name="idx_budgetincr_status_criado"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(valor_solicitado__gt=0), name="budgetincr_valor_positivo"),
        ]

    def get_transicoes_permitidas(self) -> set:
        return self.TRANSICOES.get(self.status, set())

    def __str__(self):
        return f"Recurso extra #{self.pk} — {self.rubrica} — R$ {self.valor_solicitado} [{self.status}]"


class BudgetTransfer(models.Model):
    """Remanejamento de saldo entre alocações (SGP §6.7), imutável: correção só por
    um novo remanejamento em sentido contrário."""

    class Tipo(models.TextChoices):
        ENTRE_RUBRICAS = "entre_rubricas", "Entre rubricas"
        ENTRE_TERRITORIOS = "entre_territorios", "Entre territórios"
        ENTRE_NIVEIS = "entre_niveis", "Entre níveis"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    allocation_origem = models.ForeignKey(
        BudgetAllocation, on_delete=models.PROTECT,
        related_name="transferencias_de_saida", verbose_name="Alocação de origem",
    )
    allocation_destino = models.ForeignKey(
        BudgetAllocation, on_delete=models.PROTECT,
        related_name="transferencias_de_entrada", verbose_name="Alocação de destino",
    )
    valor = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor (R$)")
    motivo = models.TextField(verbose_name="Motivo")
    documento_url = models.URLField(max_length=1024, blank=True, default="", verbose_name="Documento de respaldo")
    saldo_origem_antes = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo da origem antes")
    saldo_origem_depois = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo da origem depois")
    saldo_destino_antes = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo do destino antes")
    saldo_destino_depois = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo do destino depois")
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="remanejamentos_aprovados", verbose_name="Aprovado por",
    )
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    increase_request = models.ForeignKey(
        BudgetIncreaseRequest, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias", verbose_name="Solicitação de recurso extra",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Remanejamento"
        verbose_name_plural = "Remanejamentos"
        ordering = ["-criado_em"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("BudgetTransfer é imutável: registros existentes não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtectedError("BudgetTransfer é imutável: registros não podem ser removidos.", [self])

    def __str__(self):
        return f"[{self.tipo}] {self.allocation_origem} → {self.allocation_destino} — R$ {self.valor}"
