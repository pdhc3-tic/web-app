from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sgp.models import BudgetTransaction


def _ja_agendado(alvo: tuple) -> bool:
    """Uma transação move o mesmo alvo várias vezes, como no cancelamento em lote. Basta olhar a
    fila: o que um savepoint desfeito agendou já saiu dela."""
    return any(
        getattr(entrada[1], "alvo_do_alerta", None) == alvo
        for entrada in transaction.get_connection().run_on_commit
    )


@receiver(post_save, sender=BudgetTransaction)
def avaliar_alertas_da_movimentacao(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return
    remanejamento = instance.tipo == BudgetTransaction.Tipo.REMANEJAMENTO
    alvo = (instance.pool_id, instance.spending_limit_id, remanejamento)
    if _ja_agendado(alvo):
        return
    from apps.sgp.tasks import check_budget_thresholds

    def agendar():
        check_budget_thresholds.delay(
            pool_id=instance.pool_id, limite_id=instance.spending_limit_id,
            **({"remanejamento": True} if remanejamento else {}),
        )

    agendar.alvo_do_alerta = alvo
    # `robust`: o alerta volta na rodada diária; a falha no broker não pode derrubar a movimentação.
    transaction.on_commit(agendar, robust=True)
