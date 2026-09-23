import logging
from datetime import date, timedelta

from celery import shared_task
from django.db import connection, transaction
from django.utils import timezone

from apps.core.models.notifications import Notification
from apps.sgd.models.demand import STATUS_TERMINAIS, Demand
from apps.sgd.services.approval import responsaveis_pela_etapa_atual
from apps.sgd.services.notifications import evento_inatividade, notificar_inatividade

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
        evento = evento_inatividade(demand, referencia=referencia)
        if Notification.objects.filter(evento=evento).exists():
            continue
        responsaveis = responsaveis_pela_etapa_atual(demand)
        notificar_inatividade(demand, responsaveis, referencia=referencia)
        notificadas += 1
    return notificadas
