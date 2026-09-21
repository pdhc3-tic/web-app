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

    # Query só pega Demands ainda não-terminais — uma vez cancelada, saves
    # subsequentes da mesma Activity não a encontram mais de novo.
    from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
    from apps.sgd.services import balance as balance_service
    from apps.sgd.services import notifications as notifications_service

    demandas = Demand.objects.filter(activity=instance).exclude(status__in=STATUS_TERMINAIS)
    for demand in demandas:
        for solicitacao in demand.solicitacoes.all():
            balance_service.liberar_duas_travas(
                demand_request=solicitacao, usuario=None,
                motivo=f"Atividade vinculada em status '{instance.get_status_display()}'.",
            )
        demand.status = "cancelada"
        demand.save(update_fields=["status", "atualizado_em"])

        sigla = instance.municipio.state.sigla
        notifications_service.notificar_cancelamento_automatico(
            demand, notifications_service.usuarios_articuladores_do_estado(sigla),
        )


@receiver(post_save, sender=Activity)
def _notificar_demandas_atividade_adiada(sender, instance, **kwargs):
    """§2.3: atividade adiada mantém demandas/reservas intactas — só notifica o
    responsável pela etapa atual sobre a nova data."""
    if instance.status != "adiada" or getattr(instance, "_status_anterior", None) == "adiada":
        return

    from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
    from apps.sgd.services import notifications as notifications_service
    from apps.sgd.services.approval import responsaveis_pela_etapa_atual

    demandas = Demand.objects.filter(activity=instance).exclude(status__in=STATUS_TERMINAIS)
    for demand in demandas:
        notifications_service.notificar_atividade_adiada(
            demand, responsaveis_pela_etapa_atual(demand), nova_data=instance.data_inicio,
        )
