from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sgp.models.activity import Activity

ACTIVITY_STATUS_CANCELAM_DEMANDAS = {"cancelada", "nao_realizada"}


@receiver(post_save, sender=Activity)
def _cancelar_demandas_nao_atendidas(sender, instance, **kwargs):
    if instance.status not in ACTIVITY_STATUS_CANCELAM_DEMANDAS:
        return

    # Query só pega Demands ainda não-terminais — uma vez cancelada, saves
    # subsequentes da mesma Activity não a encontram mais de novo.
    from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
    from apps.sgd.services import balance as balance_service
    from apps.sgd.services import notifications as notifications_service
    from apps.sgd.services.approval import usuarios_articuladores_do_estado

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
            demand, usuarios_articuladores_do_estado(sigla),
        )
