"""Trilha de auditoria da demanda (SGD §10): mudanças de status e movimentações de saldo."""

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context

ENTIDADE_DEMANDA = "Demand"
ENTIDADE_MOVIMENTACAO_SALDO = "BudgetTransaction"


def registrar_status(demand, *, de, para, usuario=None) -> None:
    """`usuario=None` é ação do sistema (cancelamento automático, tasks). IP e
    User-Agent vêm do contexto da requisição, quando houver."""
    contexto = get_audit_context()
    log_audit(
        user=usuario,
        acao="demanda.criada" if de is None else "demanda.status_alterado",
        modulo="sgd",
        entidade=ENTIDADE_DEMANDA,
        entidade_id=demand.pk,
        valores_anteriores={} if de is None else {"status": de},
        valores_novos={"status": para},
        _ip=contexto["ip"],
        _user_agent=contexto["user_agent"],
    )
