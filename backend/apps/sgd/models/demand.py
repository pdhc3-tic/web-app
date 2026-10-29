from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


STATUS_CHOICES = [
    ("rascunho", "Rascunho"),
    ("submetida", "Submetida"),
    ("devolvida", "Devolvida"),
    ("pre_autorizada", "Pré-autorizada"),
    ("autorizada", "Autorizada"),
    ("em_atendimento", "Em atendimento"),
    ("concluida", "Concluída"),
    ("recusada", "Recusada"),
    ("cancelada", "Cancelada"),
]

STATUS_TERMINAIS = {"concluida", "recusada", "cancelada"}

STATUS_EDITAVEIS = {"rascunho", "devolvida"}

STATUS_CANCELAVEIS_PELO_SOLICITANTE = {"rascunho", "submetida", "devolvida", "pre_autorizada"}


class Demand(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Título")

    activity = models.ForeignKey(
        "sgp.Activity",
        on_delete=models.PROTECT,
        related_name="demandas",
        verbose_name="Atividade",
    )

    justificativa = models.TextField(
        blank=True, default="", verbose_name="Justificativa",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="rascunho",
        verbose_name="Status",
        db_index=True,
    )

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="demandas_solicitadas",
        verbose_name="Solicitante",
    )

    despesa_posterior = models.BooleanField(
        default=False,
        verbose_name="Despesa posterior à execução",
        help_text=(
            "Capturado na criação quando a atividade vinculada já estava em "
            "Em andamento/Concluída/Concluída sem evidência — sinaliza ao "
            "aprovador, não é recalculado depois."
        ),
    )

    numero_processo = models.CharField(
        max_length=64, blank=True, default="", db_index=True,
        verbose_name="Número do processo",
        help_text="Número do processo de pagamento informado pelo Arlo na importação de retorno.",
    )

    status_alterado_em = models.DateTimeField(
        default=timezone.now,
        verbose_name="Status alterado em",
        help_text=(
            "Última mudança de status — referência do alerta de inatividade. "
            "Diferente de atualizado_em, não muda em edições que mantêm o status."
        ),
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Demanda"
        verbose_name_plural = "Demandas"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["activity"], name="idx_demand_activity"),
            models.Index(fields=["status", "solicitante"], name="idx_demand_status_solic"),
            models.Index(fields=["status", "-criado_em"], name="idx_demand_status_criado"),
        ]

    def __str__(self):
        return f"{self.titulo} [{self.get_status_display()}]"

    def _total_solicitacoes(self, campo: str):
        # Com `solicitacoes` já prefetchada (listagem), soma em memória: o
        # `aggregate()` ignora o prefetch e custaria 1 query por demanda e total.
        if "solicitacoes" in getattr(self, "_prefetched_objects_cache", {}):
            return sum((getattr(s, campo) or 0 for s in self.solicitacoes.all()), Decimal("0"))
        return self.solicitacoes.aggregate(total=Sum(campo))["total"] or 0

    @property
    def valor_estimado_total(self):
        return self._total_solicitacoes("valor_estimado")

    @property
    def valor_autorizado_total(self):
        return self._total_solicitacoes("valor_autorizado")

    @property
    def valor_pago_total(self):
        return self._total_solicitacoes("valor_pago")
