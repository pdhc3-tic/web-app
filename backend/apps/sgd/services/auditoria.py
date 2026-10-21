"""Trilha de auditoria da demanda (SGD §10): mudanças de status e movimentações de saldo."""

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context

ENTIDADE_DEMANDA = "Demand"
ENTIDADE_MOVIMENTACAO_SALDO = "BudgetTransaction"


def registrar_status(demand, *, de, para, usuario=None) -> None:
    """IP e User-Agent vêm do contexto da requisição, quando houver. Sem `usuario`,
    vale o usuário do contexto (a importação do Arlo roda numa task, mas em nome
    de quem enviou o arquivo); sem nenhum dos dois, é ação do sistema."""
    contexto = get_audit_context()
    log_audit(
        user=usuario or contexto["user"],
        acao="demanda.criada" if de is None else "demanda.status_alterado",
        modulo="sgd",
        entidade=ENTIDADE_DEMANDA,
        entidade_id=demand.pk,
        valores_anteriores={} if de is None else {"status": de},
        valores_novos={"status": para},
        _ip=contexto["ip"],
        _user_agent=contexto["user_agent"],
    )


def registrar_evento(*, acao, entidade, entidade_id, usuario=None, anteriores=None, novos=None) -> None:
    """Evento de auditoria fora da demanda (recurso extra, limite individual...), com
    IP e User-Agent do contexto da requisição."""
    contexto = get_audit_context()
    log_audit(
        user=usuario or contexto["user"],
        acao=acao,
        modulo="sgd",
        entidade=entidade,
        entidade_id=entidade_id,
        valores_anteriores=anteriores or {},
        valores_novos=novos or {},
        _ip=contexto["ip"],
        _user_agent=contexto["user_agent"],
    )
