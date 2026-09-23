import logging
from datetime import date, timedelta

from celery import shared_task
from django.db import connection, transaction
from django.utils import timezone

from apps.core.models.notifications import Notification
from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
from apps.sgd.services.approval import responsaveis_pela_etapa_atual
from apps.sgd.services.notifications import EVENTO_INATIVIDADE, link_inatividade, notificar_inatividade

try:
    import sentry_sdk
except ImportError:
    class _NullSentry:
        def capture_exception(self, exc):
            return None

    sentry_sdk = _NullSentry()


logger = logging.getLogger(__name__)

DIAS_UTEIS_LIMITE = 5


def _dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias úteis (segunda–sexta) entre `inicio` (exclusive) e `fim`
    (inclusive). Sem calendário de feriados — nenhuma lib de feriados no repo."""
    dias = 0
    atual = inicio
    while atual < fim:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            dias += 1
    return dias


def _sem_contexto_de_sessao_rls(fn):
    """Roda `fn()` com a SESSION VARIABLE `app.user_role` setada como
    'super-admin' — uma task do Celery não passa pelo `SessionContextMiddleware`
    (apps/core/middleware.py), que é quem normalmente faz o `SET LOCAL` das
    variáveis que a política RLS de `sgd_demand` exige; sem isso, rodando como
    `app_user`, a policy esconderia a tabela inteira e a task nunca acharia
    nenhuma demanda parada."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.user_role = %s;", ["super-admin"])
        return fn()


@shared_task(name="sgd.tasks.check_demand_inactivity_alert")
def check_demand_inactivity_alert() -> int:
    try:
        return _sem_contexto_de_sessao_rls(_verificar_inatividade)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao verificar inatividade de demandas do SGD.")
        raise


def _verificar_inatividade() -> int:
    hoje = timezone.localdate()
    notificadas = 0
    # Rascunho nunca foi submetida — não tem "etapa atual" aguardando
    # ninguém, não faz sentido de inatividade.
    demandas = Demand.objects.exclude(
        status__in=STATUS_TERMINAIS | {"rascunho"},
    ).select_related("activity__municipio__state", "solicitante")
    for demand in demandas:
        ultima_etapa_em = demand.etapas.order_by("-criado_em").values_list(
            "criado_em", flat=True,
        ).first()
        # Resubmissão de uma Devolvida não cria ApprovalStep novo — sem o
        # max() com atualizado_em, a referência ficaria presa na data da
        # devolução antiga e o alerta dispararia cedo demais.
        referencia = max(filter(None, [ultima_etapa_em, demand.atualizado_em])).date()
        if _dias_uteis_entre(referencia, hoje) < DIAS_UTEIS_LIMITE:
            continue
        link = link_inatividade(demand, referencia=referencia)
        if Notification.objects.filter(evento=EVENTO_INATIVIDADE, link=link).exists():
            continue
        responsaveis = responsaveis_pela_etapa_atual(demand)
        notificar_inatividade(demand, responsaveis, referencia=referencia)
        notificadas += 1
    return notificadas


@shared_task(name="sgd.tasks.cancelar_demandas_da_atividade")
def cancelar_demandas_da_atividade(activity_id: int) -> int:
    """Despachada por `apps.sgd.signals.activity._cancelar_demandas_nao_atendidas`
    via `transaction.on_commit`, em vez de rodar direto no `post_save` — o
    signal roda dentro da transação de quem salvou a Activity, e setar a
    sessão privilegiada ali (ver `_sem_contexto_de_sessao_rls`) vazaria pro
    resto dessa transação, já que `SET LOCAL` não é revertido por um
    savepoint que só é liberado (não revertido)."""
    try:
        return _sem_contexto_de_sessao_rls(lambda: _cancelar_demandas_da_atividade(activity_id))
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao cancelar demandas da atividade %s.", activity_id)
        raise


def _cancelar_demandas_da_atividade(activity_id: int) -> int:
    from apps.sgd.services import balance as balance_service
    from apps.sgd.services import notifications as notifications_service
    from apps.sgd.signals.activity import ACTIVITY_STATUS_CANCELAM_DEMANDAS
    from apps.sgp.models.activity import Activity

    try:
        activity = Activity.objects.select_related("municipio__state").get(pk=activity_id)
    except Activity.DoesNotExist:
        return 0
    if activity.status not in ACTIVITY_STATUS_CANCELAM_DEMANDAS:
        # Mudou de status de novo entre o commit e a task rodar — nada a fazer.
        return 0

    # "Em atendimento" fica de fora — já está sendo atendida pela FGD, não é
    # uma "demanda não atendida" (RF10).
    demandas = Demand.objects.filter(activity=activity).exclude(
        status__in=STATUS_TERMINAIS | {"em_atendimento"}
    )
    canceladas = 0
    for demand in demandas:
        for solicitacao in demand.solicitacoes.all():
            balance_service.liberar_duas_travas(
                demand_request=solicitacao, usuario=None,
                motivo=f"Atividade vinculada em status '{activity.get_status_display()}'.",
            )
        demand.status = "cancelada"
        demand.save(update_fields=["status", "atualizado_em"])
        sigla = activity.municipio.state.sigla
        notifications_service.notificar_cancelamento_automatico(
            demand, notifications_service.usuarios_articuladores_do_estado(sigla),
        )
        canceladas += 1
    return canceladas


@shared_task(name="sgd.tasks.notificar_demandas_atividade_adiada")
def notificar_demandas_atividade_adiada(activity_id: int) -> int:
    """Mesmo motivo de `cancelar_demandas_da_atividade`: despachada via
    `transaction.on_commit` pelo signal, não rodada direto nele."""
    try:
        return _sem_contexto_de_sessao_rls(lambda: _notificar_demandas_atividade_adiada(activity_id))
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao notificar demandas da atividade adiada %s.", activity_id)
        raise


def _notificar_demandas_atividade_adiada(activity_id: int) -> int:
    from apps.sgd.services import notifications as notifications_service
    from apps.sgp.models.activity import Activity

    try:
        activity = Activity.objects.get(pk=activity_id)
    except Activity.DoesNotExist:
        return 0
    if activity.status != "adiada":
        return 0

    demandas = Demand.objects.filter(activity=activity).exclude(status__in=STATUS_TERMINAIS)
    notificadas = 0
    for demand in demandas:
        notifications_service.notificar_atividade_adiada(
            demand, responsaveis_pela_etapa_atual(demand), nova_data=activity.data_inicio,
        )
        notificadas += 1
    return notificadas
