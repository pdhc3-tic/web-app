from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PadraoFaixa(models.TextChoices):
    """Para onde cai o município sem enquadramento explícito."""

    CAPITAIS = "capitais", "Capitais sem enquadramento"
    DEMAIS = "demais", "Demais localidades"


class CategoriaBeneficiario(models.TextChoices):
    """Uma opção só, por ora: existe para replicar a diferenciação por cargo da tabela federal."""

    PADRAO = "padrao", "Padrão"


class OrigemValorDiaria(models.TextChoices):
    FEDERAL = "federal", "Tabela federal (Decreto 5.992/2006)"
    FGD = "fgd", "Valor próprio da FGD"


class FaixaDestinoDiaria(models.Model):
    """Faixa de destino do anexo do Decreto 5.992/2006. O enquadramento de município é
    dado (`EnquadramentoFaixaDiaria`), não código."""

    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome")
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    padrao = models.CharField(
        max_length=10, choices=PadraoFaixa.choices, null=True, blank=True, unique=True,
        verbose_name="Recebe os municípios sem enquadramento",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Faixa de destino de diária"
        verbose_name_plural = "Faixas de destino de diária"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class EnquadramentoFaixaDiaria(models.Model):
    """Município enquadrado explicitamente numa faixa. Pelo código IBGE, e não por FK,
    porque os municípios são carregados por comando, depois das migrations."""

    faixa = models.ForeignKey(
        FaixaDestinoDiaria, on_delete=models.CASCADE, related_name="enquadramentos", verbose_name="Faixa",
    )
    codigo_ibge = models.CharField(max_length=7, unique=True, verbose_name="Código IBGE do município")
    nome_referencia = models.CharField(max_length=150, blank=True, default="", verbose_name="Município (referência)")

    class Meta:
        verbose_name = "Enquadramento de município em faixa de diária"
        verbose_name_plural = "Enquadramentos de municípios em faixas de diária"
        ordering = ["faixa__ordem", "nome_referencia"]

    def __str__(self):
        return f"{self.nome_referencia or self.codigo_ibge} → {self.faixa}"


class TabelaDiaria(models.Model):
    """Valor da diária por faixa e categoria, com vigência. Editar cria uma nova vigência;
    a solicitação guarda o `id` da linha usada, então as linhas antigas não mudam."""

    faixa_destino = models.ForeignKey(
        FaixaDestinoDiaria, on_delete=models.PROTECT, related_name="valores", verbose_name="Faixa de destino",
    )
    categoria_beneficiario = models.CharField(
        max_length=20, choices=CategoriaBeneficiario.choices, default=CategoriaBeneficiario.PADRAO,
        verbose_name="Categoria do beneficiário",
    )
    vigencia_inicio = models.DateField(verbose_name="Início da vigência")
    vigencia_fim = models.DateField(null=True, blank=True, verbose_name="Fim da vigência")
    valor = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Valor da diária (R$)")
    origem = models.CharField(max_length=10, choices=OrigemValorDiaria.choices, verbose_name="Origem do valor")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="valores_diaria_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Valor de diária"
        verbose_name_plural = "Tabela de diárias"
        ordering = ["faixa_destino__ordem", "categoria_beneficiario", "-vigencia_inicio"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="sgd_tabela_diaria_valor_positivo"),
            models.CheckConstraint(
                condition=Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=F("vigencia_inicio")),
                name="sgd_tabela_diaria_vigencia_coerente",
            ),
        ]
        indexes = [
            models.Index(
                fields=["faixa_destino", "categoria_beneficiario", "vigencia_inicio"],
                name="sgd_tabdiaria_vigencia_idx",
            ),
        ]

    def __str__(self):
        fim = self.vigencia_fim.isoformat() if self.vigencia_fim else "…"
        return f"{self.faixa_destino} — R$ {self.valor} ({self.vigencia_inicio.isoformat()} a {fim})"
