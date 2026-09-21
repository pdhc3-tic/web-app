from __future__ import annotations

from django.conf import settings
from django.db.models import Q

from apps.core.models.notifications import Notification, TipoNotificacao
from apps.core.models.user import User


def _link_demanda(demand) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/sgd/demandas/{demand.pk}"


def usuarios_articuladores_do_estado(sigla: str):
    return User.objects.filter(
        ativo=True, profiles__perfil__slug="articulador-estadual",
    ).filter(
        Q(profiles__territorio__isnull=True) | Q(profiles__territorio__estados__contains=[sigla])
    ).distinct()


def usuarios_por_perfil(slug: str):
    return User.objects.filter(ativo=True, profiles__perfil__slug=slug).distinct()


def _notificar(*, usuarios, titulo: str, mensagem: str, link: str, evento: str, canais):
    # O envio de e-mail em si é disparado pelo post_save de Notification
    # (apps.core.models.notifications) — aqui só criamos o registro.
    for usuario in usuarios:
        for canal in canais:
            Notification.objects.create(
                user=usuario, tipo=canal, titulo=titulo, mensagem=mensagem,
                link=link, modulo_origem="sgd", evento=evento,
            )


_EMAIL_E_IN_APP = (TipoNotificacao.EMAIL, TipoNotificacao.IN_APP)
_SO_IN_APP = (TipoNotificacao.IN_APP,)


def notificar_submissao(demand, articuladores) -> None:
    _notificar(
        usuarios=articuladores,
        titulo=f"Nova demanda para pré-autorização: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi submetida e aguarda sua pré-autorização.",
        link=_link_demanda(demand), evento="demand_submetida", canais=_EMAIL_E_IN_APP,
    )


def notificar_devolucao(demand) -> None:
    _notificar(
        usuarios=[demand.solicitante],
        titulo=f"Demanda devolvida: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi devolvida para correção.",
        link=_link_demanda(demand), evento="demand_devolvida", canais=_EMAIL_E_IN_APP,
    )


def notificar_pre_autorizacao(demand, usuarios_ugp) -> None:
    _notificar(
        usuarios=usuarios_ugp,
        titulo=f"Demanda pré-autorizada aguardando autorização: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi pré-autorizada e aguarda autorização da UGP.",
        link=_link_demanda(demand), evento="demand_pre_autorizada", canais=_EMAIL_E_IN_APP,
    )


def notificar_autorizacao(demand, usuarios_fgd) -> None:
    _notificar(
        usuarios=[demand.solicitante, *usuarios_fgd],
        titulo=f"Demanda autorizada: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi autorizada.",
        link=_link_demanda(demand), evento="demand_autorizada", canais=_EMAIL_E_IN_APP,
    )


def notificar_recusa(demand) -> None:
    _notificar(
        usuarios=[demand.solicitante],
        titulo=f"Demanda recusada: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi recusada.",
        link=_link_demanda(demand), evento="demand_recusada", canais=_EMAIL_E_IN_APP,
    )


def notificar_em_atendimento(demand) -> None:
    _notificar(
        usuarios=[demand.solicitante],
        titulo=f"Demanda em atendimento: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' está em atendimento pela FGD.",
        link=_link_demanda(demand), evento="demand_em_atendimento", canais=_SO_IN_APP,
    )


def notificar_conclusao(demand) -> None:
    _notificar(
        usuarios=[demand.solicitante],
        titulo=f"Demanda concluída: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' foi concluída e encerrada com comprovante.",
        link=_link_demanda(demand), evento="demand_concluida", canais=_EMAIL_E_IN_APP,
    )


def notificar_cancelamento_automatico(demand, articuladores) -> None:
    _notificar(
        usuarios=[demand.solicitante, *articuladores],
        titulo=f"Demanda cancelada automaticamente: {demand.titulo}",
        mensagem=(
            f"A demanda '{demand.titulo}' foi cancelada automaticamente porque a "
            "atividade vinculada foi cancelada ou não realizada."
        ),
        link=_link_demanda(demand), evento="demand_cancelada_automatico", canais=_EMAIL_E_IN_APP,
    )


def notificar_mudanca_semaforo(*, usuarios, demand, rubrica_nome: str, trava: str, semaforo: str) -> None:
    _notificar(
        usuarios=usuarios,
        titulo=f"Saldo de {rubrica_nome} entrou na faixa {semaforo}",
        mensagem=f"O saldo da trava {trava} para a rubrica {rubrica_nome} entrou na faixa {semaforo}.",
        link=_link_demanda(demand), evento="demand_semaforo_mudou", canais=_EMAIL_E_IN_APP,
    )


def notificar_inatividade(demand, responsaveis) -> None:
    _notificar(
        usuarios=responsaveis,
        titulo=f"Demanda sem movimentação há 5 dias úteis: {demand.titulo}",
        mensagem=f"A demanda '{demand.titulo}' está parada em '{demand.get_status_display()}' há 5 dias úteis.",
        link=_link_demanda(demand), evento="demand_inatividade", canais=_EMAIL_E_IN_APP,
    )
