"""
Tasks assíncronas do SCA (notificações de conflito — seção 4 do SCA_Requisitos).

Executadas via Celery; em testes, `.delay()` é interceptado via mock.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.core.models.notifications import Notification, TipoNotificacao

logger = logging.getLogger(__name__)


@shared_task
def notify_articulador_sync_conflict(
    articulador_id,
    *,
    entidade="",
    uuid_local="",
    campo="",
    valor_local=None,
    valor_servidor=None,
    territorio_id=None,
):
    """Notifica o Articulador Estadual sobre conflito em campo sensível (Estratégia 3)."""
    User = get_user_model()
    try:
        articulador = User.objects.get(pk=articulador_id)
    except User.DoesNotExist:
        logger.warning("sca.notify_articulador user_not_found articulador_id=%s", articulador_id)
        return

    Notification.objects.create(
        user=articulador,
        tipo=TipoNotificacao.IN_APP,
        titulo="Conflito de sincronização em campo sensível",
        mensagem=(
            f"Conflito detectado em '{entidade}' ({campo}). "
            f"Valor local: {valor_local} | Valor no servidor: {valor_servidor}. "
            "Resolvido por last-write-wins."
        ),
        link="",
        modulo_origem="sca",
        evento="sca.sync.conflict_sensitive",
    )
    logger.info(
        "sca.notify_articulador ok articulador_id=%s entidade=%s campo=%s",
        articulador_id,
        entidade,
        campo,
    )


@shared_task
def notify_tecnico_sync_discard(*, tecnico_id, entidade="", uuid_local=""):
    """Notifica o técnico de que a modificação offline foi descartada (Estratégia 4)."""
    User = get_user_model()
    try:
        tecnico = User.objects.get(pk=tecnico_id)
    except User.DoesNotExist:
        logger.warning("sca.notify_tecnico user_not_found tecnico_id=%s", tecnico_id)
        return

    Notification.objects.create(
        user=tecnico,
        tipo=TipoNotificacao.IN_APP,
        titulo="Modificação offline descartada",
        mensagem=(
            f"O registro '{entidade}' (uuid_local={uuid_local}) foi excluído no servidor. "
            "Sua modificação local foi descartada."
        ),
        link="",
        modulo_origem="sca",
        evento="sca.sync.discarded",
    )
    logger.info(
        "sca.notify_tecnico ok tecnico_id=%s entidade=%s uuid_local=%s",
        tecnico_id,
        entidade,
        uuid_local,
    )
