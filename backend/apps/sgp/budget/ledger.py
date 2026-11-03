"""Lançamentos no ledger único do orçamento: o que muda o saldo de um pool ou de um limite."""
from __future__ import annotations

from decimal import Decimal

from apps.core.signals.audit import get_audit_context
from apps.sgp.budget.models import BudgetPool, BudgetTransaction, SpendingLimit

ZERO = Decimal("0")
Tipo = BudgetTransaction.Tipo


def efeito_no_saldo(tipo: str, valor: Decimal) -> Decimal:
    """Quanto o lançamento move o saldo disponível. A execução só converte o comprometido em
    executado: a diferença para o reservado vem num lançamento de liberação próprio."""
    if tipo in (Tipo.RESERVA, Tipo.AJUSTE):
        return -valor
    if tipo == Tipo.EXECUCAO:
        return ZERO
    return valor


def lancar(
    *, tipo: str, valor: Decimal, saldo_anterior: Decimal, saldo_posterior: Decimal, usuario,
    pool: BudgetPool | None = None, spending_limit: SpendingLimit | None = None,
    demand_request_id: str | None = None, demanda_id: str | None = None, activity_id: int | None = None,
    justificativa: str = "",
) -> BudgetTransaction:
    return BudgetTransaction.objects.create(
        pool=pool, spending_limit=spending_limit, tipo=tipo, valor=valor,
        saldo_anterior=saldo_anterior, saldo_posterior=saldo_posterior,
        demand_request_id=demand_request_id, demanda_id=demanda_id, activity_id=activity_id,
        ip=get_audit_context()["ip"], justificativa=justificativa, criado_por=usuario,
    )
