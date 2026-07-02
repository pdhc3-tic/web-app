from django.conf import settings
from django.db import models

from apps.sgp.constants import PARENTESCO_CHOICES


class MembroFamilia(models.Model):
    upf = models.ForeignKey(
        "sgp.UPF",
        on_delete=models.CASCADE,
        related_name="membros",
        verbose_name="UPF",
    )

    nome_completo = models.CharField(
        max_length=255, verbose_name="Nome Completo"
    )
    data_nasc = models.DateField(
        null=True, blank=True, verbose_name="Data de Nascimento"
    )

    cpf = models.CharField(
        max_length=11,
        blank=True,
        default="",
        verbose_name="CPF",
    )
    rg = models.CharField(
        max_length=20, blank=True, default="", verbose_name="RG"
    )
    nis = models.CharField(
        max_length=11,
        blank=True,
        default="",
        verbose_name="NIS",
    )
    caf = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="CAF",
    )

    parentesco = models.CharField(
        max_length=20,
        choices=PARENTESCO_CHOICES,
        verbose_name="Parentesco",
    )

    saude = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Condições de Saúde",
    )

    telefone = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Telefone"
    )
    email = models.EmailField(
        blank=True, default="", verbose_name="E-mail"
    )

    escolaridade = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Escolaridade",
    )
    profissao = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Profissão",
    )
    renda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Renda Mensal",
    )
    observacao = models.TextField(
        blank=True, default="", verbose_name="Observação"
    )

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
        verbose_name = "Membro da Família"
        verbose_name_plural = "Membros da Família"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["upf"],
                condition=models.Q(parentesco="titular"),
                name="unique_titular_por_upf",
            ),
        ]
        indexes = [
            models.Index(fields=["upf"], name="idx_membro_upf"),
        ]

    def __str__(self):
        return f"{self.nome_completo} ({self.get_parentesco_display()})"
