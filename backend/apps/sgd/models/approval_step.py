from django.conf import settings
from django.db import models
from django.db.models import ProtectedError


ETAPA_CHOICES = [
    ("pre_autorizacao", "Pré-autorização"),
    ("autorizacao", "Autorização"),
    ("atendimento", "Atendimento"),
]

ACAO_CHOICES = [
    ("aprovado", "Aprovado"),
    ("recusado", "Recusado"),
    ("devolvido", "Devolvido"),
    ("atendido", "Atendido"),
]


class ApprovalStep(models.Model):
    demanda = models.ForeignKey(
        "sgd.Demand",
        on_delete=models.PROTECT,
        related_name="etapas",
        verbose_name="Demanda",
    )
    etapa = models.CharField(max_length=20, choices=ETAPA_CHOICES, verbose_name="Etapa")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="etapas_demanda_decididas",
        verbose_name="Responsável",
    )
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES, verbose_name="Ação")
    justificativa = models.TextField(blank=True, default="", verbose_name="Justificativa")
    excedente_autorizado = models.BooleanField(
        default=False,
        verbose_name="Excedente autorizado",
        help_text="Marcado quando a UGP autoriza excedendo limite individual ou pool territorial (RF16).",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Etapa de Aprovação"
        verbose_name_plural = "Etapas de Aprovação"
        ordering = ["criado_em"]
        indexes = [
            models.Index(fields=["demanda", "criado_em"], name="idx_apprstep_demanda_criado"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("ApprovalStep é imutável: registros existentes não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ProtectedError("ApprovalStep é imutável: registros não podem ser removidos.", [self])

    def __str__(self):
        return f"[{self.etapa}/{self.acao}] demanda={self.demanda_id}"
