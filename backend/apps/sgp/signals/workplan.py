"""Mantém `WorkPlanAcao.quantidade_realizada` em sincronia com as Atividades.

O valor é recalculado pela regra da forma de apuração do Indicador
(`apps.sgp.services.apuracao`), e não incrementado: nas formas por soma de
UFPAs e de participantes o resultado depende dos vínculos da Atividade, não
só do status dela.
"""
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from apps.sgp.models.activity import Activity
from apps.sgp.services.apuracao import (
    recalcular_quantidade_realizada,
    recalcular_valor_executado,
)


@receiver(pre_save, sender=Activity)
def _capturar_estado_anterior(sender, instance, **kwargs):
    anterior = (
        Activity.all_objects.filter(pk=instance.pk).values("acao_id", "ativo").first()
        if instance.pk
        else None
    )
    instance._acao_anterior_id = anterior["acao_id"] if anterior else None
    instance._ativo_anterior = anterior["ativo"] if anterior else None


@receiver(post_save, sender=Activity)
def _recalcular_apos_salvar(sender, instance, **kwargs):
    acoes = {instance.acao_id, getattr(instance, "_acao_anterior_id", None)}
    recalcular_quantidade_realizada(acoes)
    # O valor executado só depende da Atividade pela Ação a que ela pertence e
    # por estar ativa; as demandas concluídas são recalculadas pelo SGD.
    if (
        getattr(instance, "_acao_anterior_id", None) != instance.acao_id
        or getattr(instance, "_ativo_anterior", None) != instance.ativo
    ):
        recalcular_valor_executado(acoes)


def _recalcular_apos_vinculos(sender, instance, action, reverse, pk_set, **kwargs):
    if not reverse:
        if action in ("post_add", "post_remove", "post_clear"):
            recalcular_quantidade_realizada({instance.acao_id})
        return

    # Alterado pelo lado da UFPA/membro. No clear o pk_set não vem, então as
    # Ações afetadas são lidas antes de os vínculos sumirem.
    vinculos = sender.objects.filter(**{instance._meta.model_name: instance})
    if action == "pre_clear":
        instance._acoes_antes_do_clear = set(
            vinculos.values_list("activity__acao_id", flat=True)
        )
    elif action == "post_clear":
        recalcular_quantidade_realizada(getattr(instance, "_acoes_antes_do_clear", set()))
    elif action in ("post_add", "post_remove"):
        recalcular_quantidade_realizada(
            Activity.all_objects.filter(pk__in=pk_set or ()).values_list("acao_id", flat=True)
        )


m2m_changed.connect(
    _recalcular_apos_vinculos,
    sender=Activity.upfs_participantes.through,
    dispatch_uid="sgp_apuracao_upfs_participantes",
)
m2m_changed.connect(
    _recalcular_apos_vinculos,
    sender=Activity.membros_participantes.through,
    dispatch_uid="sgp_apuracao_membros_participantes",
)
