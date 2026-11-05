from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sgp.models import BudgetTransaction


@receiver(post_save, sender=BudgetTransaction)
def avaliar_alertas_da_movimentacao(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.sgp.tasks import check_budget_thresholds

    argumentos = {"pool_id": instance.pool_id, "limite_id": instance.spending_limit_id}
    if instance.tipo == BudgetTransaction.Tipo.REMANEJAMENTO:
        argumentos["remanejamento"] = True
    # `robust`: o alerta volta na rodada diária; a falha no broker não pode derrubar a movimentação.
    transaction.on_commit(lambda: check_budget_thresholds.delay(**argumentos), robust=True)
