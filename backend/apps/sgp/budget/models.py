from django.conf import settings
from django.db import models
from django.db.models import ProtectedError, Q


class BudgetRubrica(models.Model):
    """Catálogo estável das rubricas orçamentárias."""

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


class BudgetPool(models.Model):
    """Saldo autônomo de uma rubrica num nível geográfico.

    `valor_comprometido` e `valor_executado` são materializados, não properties:
    atualizados exclusivamente junto de uma BudgetTransaction, dentro de transação
    atômica, para o painel não pagar uma soma por célula.
    """

    class Nivel(models.TextChoices):
        NACIONAL = "nacional", "Nacional"
        ESTADUAL = "estadual", "Estadual"
        TERRITORIAL = "territorial", "Territorial"

    rubrica = models.ForeignKey(
        BudgetRubrica,
        on_delete=models.PROTECT,
        related_name="pools",
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
        related_name="pools_orcamento",
        verbose_name="Estado",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pools_orcamento",
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
        help_text="Só em nível nacional. Uma reserva própria da UGP nunca recebe pools-filhos.",
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
        verbose_name = "Pool Orçamentário"
        verbose_name_plural = "Pools Orçamentários"
        ordering = ["rubrica", "nivel"]
        constraints = [
            models.UniqueConstraint(
                fields=["rubrica", "nivel", "estado", "territorio"],
                name="unique_budget_pool_combinacao",
                # sem isso dois NULLs em estado/territorio (nacional/estadual) não colidem no Postgres.
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                # literais, não Nivel.* — Meta não enxerga o namespace de BudgetPool.
                condition=(
                    Q(nivel="nacional", estado__isnull=True, territorio__isnull=True)
                    | Q(nivel="estadual", estado__isnull=False, territorio__isnull=True)
                    | Q(nivel="territorial", estado__isnull=True, territorio__isnull=False)
                ),
                name="ck_budget_pool_nivel_consistente",
            ),
            models.CheckConstraint(
                condition=Q(reserva_ugp=False) | Q(nivel="nacional"),
                name="ck_budget_pool_reserva_ugp_so_nacional",
            ),
            models.CheckConstraint(
                condition=Q(valor_alocado__gte=models.F("valor_comprometido") + models.F("valor_executado")),
                name="ck_budget_pool_saldo_nao_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["nivel", "territorio"], name="idx_budgetpool_nivel_territ"),
        ]

    def __str__(self):
        return f"{self.rubrica} · {self.get_nivel_display()}"


class SpendingLimit(models.Model):
    """Limite de gasto por rubrica e período: o padrão de um perfil ou a linha individual.

    A linha individual guarda o que a pessoa comprometeu e executou no período. `herdado` indica
    que ela nasceu do padrão do perfil, na primeira reserva; sem isso, é uma sobrescrita, que
    exige justificativa.
    """

    class Escopo(models.TextChoices):
        PERFIL = "perfil", "Padrão do perfil"
        INDIVIDUAL = "individual", "Individual"

    escopo = models.CharField(max_length=20, choices=Escopo.choices, verbose_name="Escopo")
    perfil = models.ForeignKey(
        "core.Role", on_delete=models.PROTECT, null=True, blank=True,
        related_name="limites_de_gasto", verbose_name="Perfil",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="limites_de_gasto", verbose_name="Usuário",
    )
    rubrica = models.ForeignKey(
        BudgetRubrica, on_delete=models.PROTECT, related_name="limites_de_gasto", verbose_name="Rubrica",
    )
    territorio = models.ForeignKey(
        "core.Territory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="limites_de_gasto", verbose_name="Território",
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
    herdado = models.BooleanField(default=False, verbose_name="Herdado do perfil")
    justificativa = models.TextField(blank=True, default="", verbose_name="Justificativa")
    periodo_inicio = models.DateField(verbose_name="Início do período")
    periodo_fim = models.DateField(verbose_name="Fim do período")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="limites_de_gasto_criados", verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Limite de Gasto"
        verbose_name_plural = "Limites de Gasto"
        ordering = ["-periodo_inicio", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(escopo="perfil", perfil__isnull=False, user__isnull=True)
                    | Q(escopo="individual", perfil__isnull=True, user__isnull=False)
                ),
                name="ck_spendinglimit_escopo_consistente",
            ),
            models.CheckConstraint(
                condition=Q(escopo="perfil") | Q(herdado=True) | ~Q(justificativa=""),
                name="ck_spendinglimit_sobrescrita_justificada",
            ),
            models.CheckConstraint(
                condition=Q(herdado=False) | Q(escopo="individual"),
                name="ck_spendinglimit_herdado_so_individual",
            ),
            models.CheckConstraint(
                condition=Q(periodo_fim__gte=models.F("periodo_inicio")),
                name="ck_spendinglimit_periodo_valido",
            ),
            models.CheckConstraint(condition=Q(valor_limite__gte=0), name="ck_spendinglimit_valor_nao_negativo"),
            models.CheckConstraint(
                condition=Q(valor_comprometido__gte=0), name="ck_spendinglimit_comprometido_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_executado__gte=0), name="ck_spendinglimit_executado_nao_negativo",
            ),
            models.UniqueConstraint(
                fields=["user", "rubrica", "periodo_inicio"],
                condition=Q(escopo="individual"),
                name="unique_spendinglimit_individual_periodo",
            ),
            models.UniqueConstraint(
                fields=["perfil", "rubrica", "periodo_inicio"],
                condition=Q(escopo="perfil"),
                name="unique_spendinglimit_perfil_periodo",
            ),
        ]

    def __str__(self):
        dono = self.user if self.escopo == self.Escopo.INDIVIDUAL else self.perfil
        return f"{dono} · {self.rubrica} — limite R$ {self.valor_limite}"

    @property
    def saldo_disponivel(self):
        return self.valor_limite - self.valor_comprometido - self.valor_executado


class BudgetTransaction(models.Model):
    """Trilha de auditoria imutável de movimentos sobre um pool.

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
        AUMENTO_LIMITE = "aumento_limite", "Alteração de limite"

    pool = models.ForeignKey(
        BudgetPool,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Pool",
    )
    spending_limit = models.ForeignKey(
        SpendingLimit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Limite de gasto",
    )
    activity = models.ForeignKey(
        "sgp.Activity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacoes_orcamento",
        verbose_name="Atividade",
        help_text="Liga o executado à Meta, pela cadeia Atividade → Ação → Meta.",
    )
    tipo = models.CharField(
        max_length=20, choices=Tipo.choices, verbose_name="Tipo",
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Valor (R$)",
    )
    saldo_anterior = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Saldo anterior (R$)",
    )
    saldo_posterior = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Saldo posterior (R$)",
    )
    demanda_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="ID da Demanda",
        help_text="Referência fraca a uma Demand do SGD (apps.sgd) — sem FK de propósito, o motor não importa apps.sgd.",
    )
    demand_request_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="ID da Solicitação",
        help_text="Referência fraca à DemandRequest do SGD: é a chave de idempotência da reserva.",
    )
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    justificativa = models.TextField(
        blank=True, default="", verbose_name="Justificativa",
    )
    # PROTECT: o trigger recusa o UPDATE que um SET_NULL faria ao apagar o usuário.
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
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
        indexes = [
            models.Index(fields=["demanda_id", "tipo"], name="idx_budgettx_demanda_tipo"),
            models.Index(fields=["demand_request_id", "tipo"], name="idx_budgettx_solicitacao_tipo"),
            models.Index(fields=["pool", "-criado_em"], name="idx_budgettx_pool_criado"),
            models.Index(fields=["spending_limit", "-criado_em"], name="idx_budgettx_limite_criado"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(pool__isnull=False, spending_limit__isnull=True)
                    | Q(pool__isnull=True, spending_limit__isnull=False)
                ),
                name="ck_budgettransaction_pool_ou_limite",
            ),
        ]

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
        return f"[{self.tipo}] {self.pool or self.spending_limit} — R$ {self.valor}"


class BudgetIncreaseRequest(models.Model):
    """Solicitação de Recurso Extra: o usuário pede aumento do próprio
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
    TERMINAIS = {Status.APROVADA, Status.APROVADA_PARCIALMENTE, Status.RECUSADA}

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
            models.UniqueConstraint(
                fields=["demanda_id", "rubrica"],
                condition=Q(demanda_id__isnull=False) & ~Q(status__in=["aprovada", "aprovada_parcialmente", "recusada"]),
                name="budgetincr_um_pedido_aberto_por_demanda_rubrica",
            ),
        ]

    def get_transicoes_permitidas(self) -> set:
        return self.TRANSICOES.get(self.status, set())

    def __str__(self):
        return f"Recurso extra #{self.pk} — {self.rubrica} — R$ {self.valor_solicitado} [{self.status}]"


class BudgetTransfer(models.Model):
    """Remanejamento de saldo entre pools, imutável: correção só por
    um novo remanejamento em sentido contrário."""

    class Tipo(models.TextChoices):
        ENTRE_RUBRICAS = "entre_rubricas", "Entre rubricas"
        ENTRE_TERRITORIOS = "entre_territorios", "Entre territórios"
        ENTRE_NIVEIS = "entre_niveis", "Entre níveis"

    class Escopo(models.TextChoices):
        PONTUAL = "pontual", "Pontual (excedente autorizado na demanda)"
        ELEVACAO_LIMITE = "elevacao_limite", "Elevação do limite individual (recurso extra)"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    escopo = models.CharField(
        max_length=20, choices=Escopo.choices, blank=True, default="", verbose_name="Escopo",
        help_text="Em branco no remanejamento feito direto entre pools, sem demanda envolvida.",
    )
    pool_origem = models.ForeignKey(
        BudgetPool, on_delete=models.PROTECT,
        related_name="transferencias_de_saida", verbose_name="Pool de origem",
    )
    pool_destino = models.ForeignKey(
        BudgetPool, on_delete=models.PROTECT,
        related_name="transferencias_de_entrada", verbose_name="Pool de destino",
    )
    valor = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor (R$)")
    motivo = models.TextField(verbose_name="Motivo")
    documento_url = models.URLField(max_length=1024, blank=True, default="", verbose_name="Documento de respaldo")
    saldo_origem_antes = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo da origem antes")
    saldo_origem_depois = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo da origem depois")
    saldo_destino_antes = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo do destino antes")
    saldo_destino_depois = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Saldo do destino depois")
    # PROTECT: o trigger recusa o UPDATE que um SET_NULL faria ao apagar o usuário.
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="remanejamentos_aprovados", verbose_name="Aprovado por",
    )
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    increase_request = models.ForeignKey(
        BudgetIncreaseRequest, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias", verbose_name="Solicitação de recurso extra",
    )
    demanda_id = models.CharField(
        max_length=64, null=True, blank=True, default=None, verbose_name="ID da Demanda",
        help_text="Referência fraca à Demand do SGD (apps.sgd), no padrão de BudgetTransaction.demanda_id.",
    )
    solicitacao_id = models.CharField(
        max_length=64, null=True, blank=True, default=None, verbose_name="ID da Solicitação",
        help_text="Referência fraca à DemandRequest que recebeu o excedente pontual (apps.sgd).",
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
        return f"[{self.tipo}] {self.pool_origem} → {self.pool_destino} — R$ {self.valor}"
