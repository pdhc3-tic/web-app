import logging

from celery import shared_task
from django.db import connection, transaction
from django.utils import timezone

from apps.core.models.notifications import Notification
from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import business_days
from apps.sgd.services.approval import marcar_cancelada, responsaveis_pela_etapa_atual
from apps.sgd.services.notifications import EVENTO_INATIVIDADE, link_inatividade, notificar_inatividade

try:
    import sentry_sdk
except ImportError:
    class _NullSentry:
        def capture_exception(self, exc):
            return None

    sentry_sdk = _NullSentry()


logger = logging.getLogger(__name__)

# Extraídos para `services/business_days.py` (reuso pelo dashboard); os nomes
# privados continuam aqui porque testes e código existente importam deles.
_feriados = business_days.feriados
_dias_uteis_entre = business_days.dias_uteis_entre
DIAS_UTEIS_LIMITE = business_days.DIAS_UTEIS_LIMITE


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
        referencia = timezone.localdate(demand.status_alterado_em)
        uf = demand.activity.municipio.state.sigla
        if _dias_uteis_entre(referencia, hoje, uf=uf) < DIAS_UTEIS_LIMITE:
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
    demandas = list(Demand.objects.filter(activity=activity).exclude(
        status__in=STATUS_TERMINAIS | {"em_atendimento"}
    ).order_by("pk"))
    # A transação é uma só: o saldo de todas as demandas sai antes de qualquer Demand
    # ser cancelada, na ordem de lock de backend/docs/orcamento.md.
    solicitacoes = list(
        DemandRequest.objects.filter(demanda__in=demandas).select_related("rubrica", "demanda__solicitante")
    )
    balance_service.liberar_duas_travas_em_lote(
        solicitacoes, usuario=None, adiar_gravacao=True,
        motivo=f"Atividade vinculada em status '{activity.get_status_display()}'.",
    )

    articuladores = notifications_service.usuarios_articuladores_do_estado(activity.municipio.state.sigla)
    for demand in demandas:
        marcar_cancelada(demand)
        notifications_service.notificar_cancelamento_automatico(demand, articuladores)
    balance_service.gravar_estado_da_reserva(solicitacoes)
    return len(demandas)


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


@shared_task(name="sgd.tasks.process_arlo_import", queue="normal")
def process_arlo_import(importacao_id: int) -> int:
    """Processa a planilha de retorno do Arlo (SGD-RF32). Fila Normal
    (Arquitetura 1.1). Devolve quantas linhas foram aplicadas com sucesso."""
    from apps.sgd.models.arlo_import import ArloImport
    from apps.sgd.services.arlo_import import processar_importacao

    try:
        importacao = ArloImport.objects.select_related("operado_por").get(pk=importacao_id)
    except ArloImport.DoesNotExist:
        logger.warning("Importação Arlo #%s não encontrada.", importacao_id)
        return 0
    if importacao.tipo != ArloImport.Tipo.IMPORTACAO or importacao.status != ArloImport.Status.PENDENTE:
        return 0
    try:
        return _sem_contexto_de_sessao_rls(lambda: processar_importacao(importacao)).registros_ok
    except Exception as exc:
        ArloImport.objects.filter(pk=importacao_id).update(
            status=ArloImport.Status.FALHOU,
            erros_json=[{"linha": 0, "erro": "Falha inesperada ao processar o arquivo."}],
        )
        sentry_sdk.capture_exception(exc)
        logger.exception("Falha ao processar a importação Arlo #%s.", importacao_id)
        raise
