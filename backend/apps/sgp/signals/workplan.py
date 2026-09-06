from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.sgp.models.activity import Activity
from apps.sgp.models.workplan import WorkPlanAcao


def _conta_para_progresso(status: str, ativo: bool) -> bool:
    """Semântica do progresso materializado: concluído e não soft-deletado."""
    return status == "concluido" and ativo


@receiver(pre_save, sender=Activity)
def _capturar_estado_anterior_progresso(sender, instance, **kwargs):
    anterior = None
    if instance.pk:
        anterior = (
            Activity.objects.filter(pk=instance.pk)
            .values("status", "ativo", "acao_id")
            .first()
        )
    instance._progresso_anterior = (
        (anterior["acao_id"], _conta_para_progresso(anterior["status"], anterior["ativo"]))
        if anterior
        else (None, False)
    )


@receiver(post_save, sender=Activity)
def _atualizar_quantidade_realizada(sender, instance, **kwargs):
    """Mantém WorkPlanAcao.quantidade_realizada em sincronia com as Atividades (issue #229)."""
    acao_anterior_id, contava_antes = getattr(
        instance, "_progresso_anterior", (None, False)
    )
    conta_agora = _conta_para_progresso(instance.status, instance.ativo)
    acao_atual_id = instance.acao_id

    if acao_anterior_id == acao_atual_id:
        delta = (1 if conta_agora else 0) - (1 if contava_antes else 0)
        if delta:
            WorkPlanAcao.objects.filter(pk=acao_atual_id).update(
                quantidade_realizada=F("quantidade_realizada") + delta
            )
        return

    if contava_antes and acao_anterior_id is not None:
        WorkPlanAcao.objects.filter(pk=acao_anterior_id).update(
            quantidade_realizada=F("quantidade_realizada") - 1
        )
    if conta_agora:
        WorkPlanAcao.objects.filter(pk=acao_atual_id).update(
            quantidade_realizada=F("quantidade_realizada") + 1
        )
