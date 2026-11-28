from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, ProtectedError, Q


class TED(models.Model):
    """Termo de Execução Descentralizada do projeto. Valor global e vigência
    espelham a versão vigente e só mudam com o registro de uma nova versão."""

    numero = models.CharField(max_length=100, unique=True, verbose_name="Número do TED")
    participes = ArrayField(
        models.CharField(max_length=255), default=list, verbose_name="Partícipes",
    )
    objeto = models.TextField(blank=True, default="", verbose_name="Objeto")
    valor_global = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name="Valor Global (R$)",
    )
    vigencia_inicio = models.DateField(null=True, blank=True, verbose_name="Início da Vigência")
    vigencia_fim = models.DateField(null=True, blank=True, verbose_name="Fim da Vigência")
    versao_vigente = models.OneToOneField(
        "sgp.TEDVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Versão Vigente",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "TED"
        verbose_name_plural = "TEDs"
        ordering = ["pk"]

    def __str__(self):
        return f"TED {self.numero}"


class TEDVersion(models.Model):
    """Versão do plano aprovado. Cada aditivo ou prorrogação gera uma nova e
    as anteriores ficam como estavam."""

    class Tipo(models.TextChoices):
        ORIGINAL = "original", "Original"
        ADITIVO = "aditivo", "Termo Aditivo"
        PRORROGACAO = "prorrogacao", "Prorrogação"

    ted = models.ForeignKey(
        TED, on_delete=models.PROTECT, related_name="versoes", verbose_name="TED",
    )
    numero_versao = models.PositiveSmallIntegerField(verbose_name="Número da Versão")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    motivo = models.TextField(blank=True, default="", verbose_name="Motivo")
    vigencia_inicio = models.DateField(verbose_name="Início da Vigência")
    vigencia_fim = models.DateField(verbose_name="Fim da Vigência")
    valor_global = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Valor Global (R$)",
    )
    plano_snapshot = models.JSONField(default=dict, verbose_name="Plano de Trabalho Aprovado")
    documento_key = models.CharField(max_length=255, unique=True, verbose_name="Documento (PDF)")
    # PROTECT: a versão é imutável, e um SET_NULL apagaria quem a registrou.
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Registrado por",
    )
    registrado_em = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Versão do TED"
        verbose_name_plural = "Versões do TED"
        ordering = ["ted", "numero_versao"]
        constraints = [
            models.UniqueConstraint(
                fields=["ted", "numero_versao"], name="unique_ted_numero_versao",
            ),
            models.UniqueConstraint(
                # literal, não Tipo.ORIGINAL — Meta não enxerga o namespace da classe.
                fields=["ted"], condition=Q(tipo="original"), name="unique_ted_versao_original",
            ),
            models.CheckConstraint(
                condition=Q(vigencia_fim__gt=F("vigencia_inicio")),
                name="ck_ted_versao_vigencia_valida",
            ),
            models.CheckConstraint(
                condition=Q(valor_global__gte=0), name="ck_ted_versao_valor_global_nao_negativo",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("TEDVersion é imutável: versões registradas não podem ser alteradas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtectedError("TEDVersion é imutável: versões registradas não podem ser removidas.", [self])

    def __str__(self):
        return f"{self.ted} · versão {self.numero_versao} ({self.get_tipo_display()})"


class TEDVersionRubrica(models.Model):
    """Valor aprovado para uma rubrica numa versão do TED. Rubrica sem linha
    na versão tem aprovado zero."""

    versao = models.ForeignKey(
        TEDVersion, on_delete=models.PROTECT, related_name="rubricas", verbose_name="Versão",
    )
    rubrica = models.ForeignKey(
        "sgp.BudgetRubrica", on_delete=models.PROTECT, related_name="+", verbose_name="Rubrica",
    )
    valor_aprovado = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Valor Aprovado (R$)",
    )

    class Meta:
        verbose_name = "Rubrica da Versão do TED"
        verbose_name_plural = "Rubricas da Versão do TED"
        ordering = ["versao", "rubrica__ordem"]
        constraints = [
            models.UniqueConstraint(fields=["versao", "rubrica"], name="unique_ted_versao_rubrica"),
            models.CheckConstraint(
                condition=Q(valor_aprovado__gte=0), name="ck_ted_versao_rubrica_nao_negativo",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("A distribuição por rubrica de uma versão do TED é imutável.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtectedError("A distribuição por rubrica de uma versão do TED é imutável.", [self])

    def __str__(self):
        return f"{self.versao} · {self.rubrica}: R$ {self.valor_aprovado}"
