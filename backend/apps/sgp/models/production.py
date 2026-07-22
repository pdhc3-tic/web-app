from django.core.exceptions import ValidationError
from django.db import models


class Production(models.Model):
    TIPO_AGRICOLA = "agricola"
    TIPO_PECUARIA = "pecuaria"
    TIPO_OUTRA = "outra"

    TIPO_CHOICES = [
        (TIPO_AGRICOLA, "Agrícola"),
        (TIPO_PECUARIA, "Pecuária"),
        (TIPO_OUTRA, "Outra"),
    ]

    SISTEMA_EXTENSIVO = "extensivo"
    SISTEMA_SEMI_INTENSIVO = "semi_intensivo"
    SISTEMA_INTENSIVO = "intensivo"

    SISTEMA_CRIACAO_CHOICES = [
        (SISTEMA_EXTENSIVO, "Extensivo"),
        (SISTEMA_SEMI_INTENSIVO, "Semi-intensivo"),
        (SISTEMA_INTENSIVO, "Intensivo"),
    ]

    TIPO_OUTRA_ARTESANATO = "artesanato"
    TIPO_OUTRA_BENEFICIAMENTO = "beneficiamento"
    TIPO_OUTRA_EXTRATIVISMO = "extrativismo"
    TIPO_OUTRA_OUTRO = "outro"

    TIPO_OUTRA_CHOICES = [
        (TIPO_OUTRA_ARTESANATO, "Artesanato"),
        (TIPO_OUTRA_BENEFICIAMENTO, "Beneficiamento"),
        (TIPO_OUTRA_EXTRATIVISMO, "Extrativismo"),
        (TIPO_OUTRA_OUTRO, "Outro"),
    ]

    upf = models.ForeignKey(
        "sgp.UPF",
        on_delete=models.CASCADE,
        related_name="producoes",
        verbose_name="UPF",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name="Tipo",
    )

    cultura = models.ForeignKey(
        "sgp.Cultura",
        on_delete=models.PROTECT,
        related_name="producoes",
        null=True,
        blank=True,
        verbose_name="Cultura",
    )
    area_ha = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Área (ha)",
    )
    producao_estimada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Produção Estimada",
    )
    unidade_producao = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Unidade de Produção",
    )
    sementes_crioulas = models.BooleanField(
        default=False,
        verbose_name="Sementes Crioulas",
    )

    especie = models.ForeignKey(
        "sgp.EspecieAnimal",
        on_delete=models.PROTECT,
        related_name="producoes",
        null=True,
        blank=True,
        verbose_name="Espécie Animal",
    )
    n_matrizes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Matrizes",
    )
    n_reprodutores = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Reprodutores",
    )
    n_jovens = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Jovens",
    )
    area_pastejo_ha = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Área de Pastejo (ha)",
    )
    sistema_criacao = models.CharField(
        max_length=20,
        choices=SISTEMA_CRIACAO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sistema de Criação",
    )

    tipo_outra = models.CharField(
        max_length=20,
        choices=TIPO_OUTRA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Outra Atividade",
    )
    descricao_outra = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição da Outra Atividade",
    )
    quantidade_produzida = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        verbose_name="Quantidade Produzida",
    )
    renda_estimada_mensal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Renda Estimada Mensal",
    )

    custo_anual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Custo Anual",
    )
    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Produção"
        verbose_name_plural = "Produções"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["upf"], name="idx_production_upf"),
        ]

    def clean(self):
        errors = {}
        if self.tipo == self.TIPO_AGRICOLA:
            if not self.cultura_id:
                errors["cultura"] = "Cultura é obrigatória para produção agrícola."
            if self.especie_id:
                errors["especie"] = "Espécie deve ser nula para produção agrícola."
            if self.tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção agrícola."
        elif self.tipo == self.TIPO_PECUARIA:
            if not self.especie_id:
                errors["especie"] = "Espécie é obrigatória para produção pecuária."
            if self.cultura_id:
                errors["cultura"] = "Cultura deve ser nula para produção pecuária."
            if self.tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção pecuária."
        elif self.tipo == self.TIPO_OUTRA:
            if not self.tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade é obrigatório."
            if self.cultura_id:
                errors["cultura"] = "Cultura deve ser nula para outra atividade."
            if self.especie_id:
                errors["especie"] = "Espécie deve ser nula para outra atividade."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.get_tipo_display()} - UPF {self.upf_id}"
