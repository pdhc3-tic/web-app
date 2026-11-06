from django.db import models


class TipoSolicitacao(models.Model):
    """Catálogo de tipos de solicitação, mantido pelo Super Admin. A rubrica é atribuída
    à `DemandRequest` na criação: alterá-la aqui não afeta solicitações já existentes."""

    slug = models.SlugField(max_length=50, unique=True, verbose_name="Identificador")
    nome = models.CharField(max_length=100, verbose_name="Nome")
    rubrica = models.ForeignKey(
        "sgp.BudgetRubrica",
        on_delete=models.PROTECT,
        related_name="tipos_solicitacao_sgd",
        verbose_name="Rubrica",
    )
    schema_campos = models.JSONField(default=dict, blank=True, verbose_name="Campos do formulário (JSON Schema)")
    validador = models.CharField(max_length=50, blank=True, default="", verbose_name="Validador")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tipo de solicitação"
        verbose_name_plural = "Tipos de solicitação"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome
