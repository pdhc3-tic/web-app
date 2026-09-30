import re
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Cast
from django.utils import timezone

from apps.sgp.constants import STATUS_CONCLUIDA, STATUS_EM_ATRASO, STATUS_NO_PRAZO

CEM = Decimal("100")
CENTAVO = Decimal("0.01")


def validate_numero_submeta(value):
    if not re.match(r"^\d+\.\d+$", value):
        raise ValidationError("Formato inválido. Use X.Y (ex: 1.1, 2.3).")


def validate_numero_acao(value):
    if not re.match(r"^\d+\.\d+\.\d+$", value):
        raise ValidationError("Formato inválido. Use X.Y.Z (ex: 1.1.1, 2.3.4).")


# Ordena números X.Y e X.Y.Z como números ("1.2" antes de "1.10") no banco.
NUMERO_EM_ORDEM = Cast(
    models.Func(models.F("numero"), models.Value("."), function="string_to_array"),
    output_field=ArrayField(models.IntegerField()),
)


# Cálculos de execução do Plano de Trabalho. Os properties dos models e o
# painel/exportação (que apuram só o escopo do usuário) usam as mesmas funções.

def status_execucao(concluida: bool, data_fim, hoje=None) -> str:
    if concluida:
        return STATUS_CONCLUIDA
    if data_fim and (hoje or timezone.localdate()) > data_fim:
        return STATUS_EM_ATRASO
    return STATUS_NO_PRAZO


def status_da_meta(submetas_concluidas: list[bool], data_fim, hoje=None) -> str:
    """Status da Meta calculado com base nas Submetas (SGP §5.2): um item por
    Submeta, dizendo se ela está concluída."""
    if not submetas_concluidas:
        return STATUS_NO_PRAZO
    return status_execucao(all(submetas_concluidas), data_fim, hoje)


def percentual(parte, total) -> Decimal:
    """Sem arredondar, para comparar com limiares; exibição passa por `arredondar`."""
    if total <= 0:
        return Decimal("0")
    return Decimal(parte) / Decimal(total) * CEM


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def custo_unitario(valor_executado, quantidade_realizada) -> Decimal | None:
    if not quantidade_realizada:
        return None
    return arredondar(Decimal(valor_executado) / Decimal(quantidade_realizada))


def valores_gravados(instancia, *campos) -> dict | None:
    """Campos como estão no banco, para comparar com a instância em edição;
    None para registro ainda não salvo."""
    if not instancia.pk:
        return None
    return type(instancia).objects.filter(pk=instancia.pk).values(*campos).first()


def _erros_no_pai(filho, pai, nome: str, nome_do_pai: str) -> dict:
    """Número com o prefixo do pai e período contido no dele (Submeta na Meta,
    Ação na Submeta). `pai` é None enquanto o vínculo não foi informado."""
    erros = {}
    if pai is not None and filho.numero and not filho.numero.startswith(f"{pai.numero}."):
        erros["numero"] = (
            f"O número da {nome} deve começar com {pai.numero}. (número da {nome_do_pai})."
        )
    if filho.data_inicio and filho.data_fim and filho.data_inicio > filho.data_fim:
        erros["data_fim"] = "A data de término não pode ser anterior à de início."
    elif pai is not None and filho.data_inicio and filho.data_fim and (
        filho.data_inicio < pai.data_inicio or filho.data_fim > pai.data_fim
    ):
        erros["data_inicio"] = (
            f"O período da {nome} deve estar contido no período da {nome_do_pai} "
            f"({pai.data_inicio:%d/%m/%Y} a {pai.data_fim:%d/%m/%Y})."
        )
    return erros


def _filhos_fora_do_periodo(filhos, data_inicio, data_fim) -> list[str]:
    """Números dos filhos (Submetas ou Ações) que o período deixaria de fora."""
    if not (data_inicio and data_fim):
        return []
    return list(
        filhos.exclude(data_inicio__gte=data_inicio, data_fim__lte=data_fim)
        .order_by(NUMERO_EM_ORDEM)
        .values_list("numero", flat=True)
    )


class WorkPlanMeta(models.Model):
    numero = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        unique=True,
        verbose_name="Número",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(
        blank=True, default="", verbose_name="Descrição"
    )
    ods_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ODS",
        help_text="Lista de IDs dos Objetivos de Desenvolvimento Sustentável (1–17).",
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Meta do Plano de Trabalho"
        verbose_name_plural = "Metas do Plano de Trabalho"
        ordering = ["numero"]
        indexes = [
            models.Index(fields=["numero"], name="idx_wpmeta_numero"),
        ]

    def __str__(self):
        return f"Meta {self.numero} – {self.titulo}"

    def clean(self):
        if not self.pk:
            return
        erros = {}
        gravado = valores_gravados(self, "numero")
        if gravado and gravado["numero"] != self.numero and self.submetas.exists():
            erros["numero"] = (
                "Não é possível mudar o número de uma Meta que já tem Submetas: "
                "a numeração delas começa com o número da Meta."
            )
        fora = _filhos_fora_do_periodo(self.submetas.all(), self.data_inicio, self.data_fim)
        if fora:
            erros["data_inicio"] = f"O novo período deixa Submetas fora da Meta: {', '.join(fora)}."
        if erros:
            raise ValidationError(erros)

    @property
    def valor_total_planejado(self):
        return sum((s.valor_total for s in self.submetas.all()), Decimal("0"))

    @property
    def quantidade_planejada(self):
        return sum((s.quantidade_planejada for s in self.submetas.all()), Decimal("0"))

    @property
    def valor_executado(self):
        return sum((s.valor_executado for s in self.submetas.all()), Decimal("0"))

    @property
    def status_calculado(self):
        return status_da_meta(
            [s.status_execucao == STATUS_CONCLUIDA for s in self.submetas.all()], self.data_fim
        )


class WorkPlanSubmeta(models.Model):
    """2º nível do Plano de Trabalho (X.Y): agrupa Ações afins de uma Meta e
    consolida quantidades e valores por soma delas. Não tem orçamento próprio."""

    meta = models.ForeignKey(
        WorkPlanMeta,
        on_delete=models.CASCADE,
        related_name="submetas",
        verbose_name="Meta",
    )
    numero = models.CharField(
        max_length=10,
        validators=[validate_numero_submeta],
        verbose_name="Número",
        help_text="Numeração X.Y, com X igual ao número da Meta.",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(blank=True, default="", verbose_name="Descrição")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submetas_responsavel",
        verbose_name="Responsável",
        help_text="Usuário da UGP que acompanha a Submeta.",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Submeta do Plano de Trabalho"
        verbose_name_plural = "Submetas do Plano de Trabalho"
        ordering = ["meta", NUMERO_EM_ORDEM]
        constraints = [
            models.UniqueConstraint(
                fields=["meta", "numero"], name="unique_numero_submeta_por_meta",
            ),
        ]
        indexes = [
            models.Index(fields=["meta"], name="idx_wpsubmeta_meta"),
        ]

    def __str__(self):
        return f"{self.numero} – {self.titulo}"

    def clean(self):
        from apps.core.services.permissions import user_has_role

        erros = _erros_no_pai(self, self.meta if self.meta_id else None, "Submeta", "Meta")
        gravado = valores_gravados(self, "numero", "meta_id")
        if (
            gravado
            and (gravado["numero"], gravado["meta_id"]) != (self.numero, self.meta_id)
            and self.acoes.exists()
        ):
            erros["numero"] = (
                "Não é possível mudar o número nem a Meta de uma Submeta que já tem Ações: "
                "a numeração delas começa com o número da Submeta."
            )
        if self.responsavel_id and not user_has_role(self.responsavel, "ugp"):
            erros["responsavel"] = "O responsável precisa ser um usuário da UGP."
        if self.pk and not erros.keys() & {"data_inicio", "data_fim"}:
            fora = _filhos_fora_do_periodo(self.acoes.all(), self.data_inicio, self.data_fim)
            if fora:
                erros["data_inicio"] = (
                    f"O novo período deixa Ações fora da Submeta: {', '.join(fora)}."
                )
        if erros:
            raise ValidationError(erros)

    @property
    def quantidade_planejada(self):
        return sum((a.quantidade_planejada for a in self.acoes.all()), Decimal("0"))

    @property
    def quantidade_realizada(self):
        return sum((a.quantidade_realizada for a in self.acoes.all()), 0)

    @property
    def valor_total(self):
        return sum((a.valor_total for a in self.acoes.all()), Decimal("0"))

    @property
    def valor_executado(self):
        return sum((a.valor_executado for a in self.acoes.all()), Decimal("0"))

    @property
    def status_execucao(self):
        acoes = list(self.acoes.all())
        return status_execucao(
            bool(acoes) and all(a.status_execucao == STATUS_CONCLUIDA for a in acoes),
            self.data_fim,
        )


class WorkPlanAcao(models.Model):
    submeta = models.ForeignKey(
        WorkPlanSubmeta,
        on_delete=models.PROTECT,
        related_name="acoes",
        verbose_name="Submeta",
    )
    # Derivada da Submeta no save(). Continua gravada porque o orçamento
    # (BudgetAllocation.meta), o SGD e os filtros por Meta leem dela.
    meta = models.ForeignKey(
        WorkPlanMeta,
        on_delete=models.CASCADE,
        related_name="acoes",
        verbose_name="Meta",
        editable=False,
    )
    indicador = models.ForeignKey(
        "sgp.Indicator",
        on_delete=models.PROTECT,
        related_name="acoes",
        verbose_name="Indicador",
    )
    numero = models.CharField(
        max_length=12,
        validators=[validate_numero_acao],
        verbose_name="Número",
        help_text="Numeração X.Y.Z, com X.Y igual ao número da Submeta.",
    )
    descricao = models.CharField(
        max_length=500, verbose_name="Descrição"
    )
    quantidade_planejada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(
            Decimal("0.01"), message="A quantidade planejada precisa ser maior que zero."
        )],
        verbose_name="Quantidade Planejada",
    )
    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0, message="O valor unitário não pode ser negativo.")],
        verbose_name="Valor Unitário (R$)",
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    quantidade_realizada = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantidade Realizada",
        help_text=(
            "Apurada conforme a forma de apuração do Indicador e mantida por "
            "apps.sgp.signals.workplan; na forma manual, lançada pela UGP. "
            "Use `manage.py verificar_progresso_acoes` para reconciliar."
        ),
    )

    valor_executado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Valor Executado (R$)",
        help_text=(
            "Soma do valor pago nas demandas concluídas das Atividades da Ação. "
            "Mantido por apps.sgp.services.apuracao.recalcular_valor_executado."
        ),
    )

    rubricas_previstas = models.ManyToManyField(
        "sgp.BudgetRubrica",
        blank=True,
        related_name="acoes_previstas",
        verbose_name="Rubricas previstas",
        help_text=(
            "Rubricas orçamentárias esperadas para esta Ação — usado pelo SGD "
            "(RF23) pra alertar quando uma solicitação usa rubrica fora do "
            "previsto. Vazio = sem previsão cadastrada, não gera alerta."
        ),
    )

    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Ação do Plano de Trabalho"
        verbose_name_plural = "Ações do Plano de Trabalho"
        ordering = ["meta", NUMERO_EM_ORDEM]
        constraints = [
            models.UniqueConstraint(
                fields=["submeta", "numero"],
                name="unique_numero_acao_por_submeta",
            ),
        ]
        indexes = [
            models.Index(fields=["meta"], name="idx_wpacao_meta"),
            models.Index(fields=["submeta"], name="idx_wpacao_submeta"),
            models.Index(fields=["indicador"], name="idx_wpacao_indicador"),
        ]

    def __str__(self):
        return f"{self.numero} – {self.descricao}"

    def save(self, *args, **kwargs):
        if self.submeta_id:
            self.meta_id = WorkPlanSubmeta.objects.values_list("meta_id", flat=True).get(
                pk=self.submeta_id
            )
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "submeta" in update_fields:
                kwargs["update_fields"] = {*update_fields, "meta"}
        super().save(*args, **kwargs)

    def clean(self):
        erros = _erros_no_pai(self, self.submeta if self.submeta_id else None, "Ação", "Submeta")
        if self.indicador_id and not self.indicador.ativo:
            # Ação que já usa um Indicador inativo continua válida; só não se
            # vincula (nem se troca para) um inativo.
            gravado = valores_gravados(self, "indicador_id")
            if not gravado or gravado["indicador_id"] != self.indicador_id:
                erros["indicador"] = "Indicador inativo não pode ser vinculado a uma Ação."
        if erros:
            raise ValidationError(erros)

    @property
    def valor_total(self):
        return self.quantidade_planejada * self.valor_unitario

    @property
    def percentual_realizado(self):
        return arredondar(percentual(self.quantidade_realizada, self.quantidade_planejada))

    @property
    def custo_unitario_realizado(self):
        return custo_unitario(self.valor_executado, self.quantidade_realizada)

    @property
    def status_execucao(self):
        return status_execucao(
            self.quantidade_realizada >= self.quantidade_planejada, self.data_fim
        )
