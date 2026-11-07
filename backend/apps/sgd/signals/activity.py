from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.sgp.models.activity import Activity

ACTIVITY_STATUS_CANCELAM_DEMANDAS = {"cancelada", "nao_realizada"}
ACTIVITY_STATUS_SEM_EVIDENCIA = "concluido_sem_evidencia"


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
    if getattr(instance, "_status_anterior", None) in ACTIVITY_STATUS_CANCELAM_DEMANDAS:
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


@receiver(post_save, sender=Activity)
def _registrar_riscos_da_atividade_sem_evidencia(sender, instance, **kwargs):
    if instance.status != ACTIVITY_STATUS_SEM_EVIDENCIA:
        return
    if getattr(instance, "_status_anterior", None) == ACTIVITY_STATUS_SEM_EVIDENCIA:
        return

    # Na mesma transação, e não em tarefa: o status é terminal e não há outra chance de registrar
    # se o broker estiver fora. A visão total devolve o papel da sessão ao terminar.
    from apps.sgd.services import workflow as workflow_service
    workflow_service.registrar_riscos_da_atividade_sem_evidencia(instance.pk)
