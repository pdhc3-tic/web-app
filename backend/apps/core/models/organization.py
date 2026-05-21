from django.db import models


class TipoOrganizacao(models.TextChoices):
    ASSOCIACAO = "ASSOCIACAO", "Associação"
    COOPERATIVA = "COOPERATIVA", "Cooperativa"
    FUNDACAO = "FUNDACAO", "Fundação"
    OUTRO = "OUTRO", "Outro"


class Organization(models.Model):
    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, unique=True)
    tipo = models.CharField(
        max_length=20,
        choices=TipoOrganizacao.choices,
        default=TipoOrganizacao.OUTRO,
    )
    municipio = models.ForeignKey(
        "core.Municipality",
        on_delete=models.PROTECT,
        related_name="organizations",
    )
    territorios = models.ManyToManyField(
        "core.Territory",
        blank=True,
        related_name="organizations",
    )
    contato = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefone = models.CharField(max_length=20, blank=True, default="")
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["ativa"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"
