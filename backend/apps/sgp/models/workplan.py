import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sgp.constants import TIPO_UNIDADE_MEDIDA


def validate_numero_acao(value):
    if not re.match(r"^\d+\.\d+$", value):
        raise ValidationError(
            "Formato inválido. Use X.Y (ex: 1.1, 2.3)."
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

    @property
    def valor_total_planejado(self):
        from django.db.models import F
        return self.acoes.aggregate(
            total=models.Sum(F("quantidade_planejada") * F("valor_unitario"))
        )["total"] or 0

    @property
    def status_calculado(self):
        acoes = list(self.acoes.all())
        if not acoes:
            return "no_prazo"
        if all(a.status_execucao == "concluida" for a in acoes):
            return "concluida"
        if timezone.localdate() > self.data_fim:
            return "em_atraso"
        return "no_prazo"


class WorkPlanAcao(models.Model):
    meta = models.ForeignKey(
        WorkPlanMeta,
        on_delete=models.CASCADE,
        related_name="acoes",
        verbose_name="Meta",
    )
    numero = models.CharField(
        max_length=10,
        validators=[validate_numero_acao],
        verbose_name="Número",
        help_text="Numeração X.Y (ex: 1.1, 1.2).",
    )
    descricao = models.CharField(
        max_length=500, verbose_name="Descrição"
    )
    tipo_unidade = models.PositiveSmallIntegerField(
        choices=TIPO_UNIDADE_MEDIDA,
        verbose_name="Tipo de Unidade",
    )
    quantidade_planejada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Quantidade Planejada",
    )
    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor Unitário (R$)",
    )
    data_inicio = models.DateField(
        null=True, blank=True, verbose_name="Data de Início"
    )
    data_fim = models.DateField(
        null=True, blank=True, verbose_name="Data de Término"
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
        ordering = ["meta", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["meta", "numero"],
                name="unique_numero_acao_por_meta",
            ),
        ]
        indexes = [
            models.Index(fields=["meta"], name="idx_wpacao_meta"),
        ]

    def __str__(self):
        return f"{self.numero} – {self.descricao}"

    @property
    def valor_total(self):
        return self.quantidade_planejada * self.valor_unitario

    @property
    def quantidade_realizada(self):
        return 0

    @property
    def status_execucao(self):
        if self.quantidade_realizada >= self.quantidade_planejada:
            return "concluida"
        if self.data_fim and timezone.localdate() > self.data_fim:
            return "em_atraso"
        return "no_prazo"
