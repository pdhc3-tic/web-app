from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.sgp.models.activity import Activity

ACTIVITY_STATUS_CANCELAM_DEMANDAS = {"cancelada", "nao_realizada"}


@receiver(pre_save, sender=Activity)
def _capturar_status_anterior(sender, instance, **kwargs):
    # Necessário pra `_notificar_demandas_atividade_adiada` só disparar na
    # transição *para* "adiada", não em todo save subsequente enquanto
    # permanece adiada — mesmo padrão de apps.sgp.signals.workplan.
    instance._status_anterior = (
        Activity.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        if instance.pk else None
    )


@receiver(post_save, sender=Activity)
def _cancelar_demandas_nao_atendidas(sender, instance, **kwargs):
    if instance.status not in ACTIVITY_STATUS_CANCELAM_DEMANDAS:
        return

    # Despachada via Celery depois do commit, não executada direto aqui: a
    # query de Demand vinculadas passa pela política RLS de sgd_demand, que
    # só enxerga tudo com a sessão certa setada (ver apps.sgd.tasks); fazer
    # esse SET LOCAL aqui, no meio da transação de quem salvou a Activity,
    # vazaria a sessão privilegiada pro resto dela (SET LOCAL sobrevive a um
    # savepoint liberado, só é desfeito num rollback pra ele).
    from apps.sgd.tasks import cancelar_demandas_da_atividade
    transaction.on_commit(lambda: cancelar_demandas_da_atividade.delay(instance.pk))


@receiver(post_save, sender=Activity)
def _notificar_demandas_atividade_adiada(sender, instance, **kwargs):
    """§2.3: atividade adiada mantém demandas/reservas intactas — só notifica o
    responsável pela etapa atual sobre a nova data."""
    if instance.status != "adiada" or getattr(instance, "_status_anterior", None) == "adiada":
        return

    from apps.sgd.tasks import notificar_demandas_atividade_adiada
    transaction.on_commit(lambda: notificar_demandas_atividade_adiada.delay(instance.pk))
