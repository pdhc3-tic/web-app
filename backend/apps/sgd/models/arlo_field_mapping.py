from django.db import models


class ArloFieldMapping(models.Model):
    """Mapeamento campo do SGD <-> coluna da planilha do Arlo (SGD §6).

    Na exportação, `ordem` define a posição da coluna no CSV; na importação,
    a ordem é irrelevante (as colunas são localizadas pelo nome do cabeçalho).
    """

    class Direcao(models.TextChoices):
        EXPORTACAO = "exportacao", "Exportação (SGD → Arlo)"
        IMPORTACAO = "importacao", "Importação (Arlo → SGD)"

    class Formato(models.TextChoices):
        TEXTO = "texto", "Texto"
        DATA = "data", "Data"
        MOEDA = "moeda", "Moeda"

    direcao = models.CharField(max_length=12, choices=Direcao.choices, verbose_name="Direção")
    campo_sgd = models.CharField(max_length=64, verbose_name="Campo do SGD")
    coluna_arlo = models.CharField(max_length=128, verbose_name="Coluna no Arlo")
    formato = models.CharField(max_length=8, choices=Formato.choices, default=Formato.TEXTO, verbose_name="Formato")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Mapeamento de campo Arlo"
        verbose_name_plural = "Mapeamentos de campos Arlo"
        ordering = ["direcao", "ordem", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["direcao", "campo_sgd"], name="uq_arlo_map_direcao_campo"),
            models.UniqueConstraint(fields=["direcao", "coluna_arlo"], name="uq_arlo_map_direcao_coluna"),
        ]

    def __str__(self):
        return f"{self.get_direcao_display()}: {self.campo_sgd} ↔ {self.coluna_arlo}"
