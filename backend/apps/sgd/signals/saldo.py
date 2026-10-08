from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context
from apps.sgd.models import DemandRequest
from apps.sgd.services.auditoria import ENTIDADE_MOVIMENTACAO_SALDO
from apps.sgp.models import BudgetTransaction
from apps.sgp.services.budget import _valor_total_reservado

Tipo = BudgetTransaction.Tipo
ZERO = Decimal("0")


def _efeito_na_alocacao(transacao) -> dict:
    """Quanto a transação moveu de cada saldo da alocação. As alocações já foram
    salvas quando a transação nasce, então o saldo anterior é o posterior
    desfeito esse efeito."""
    valor = transacao.valor
    if transacao.tipo in (Tipo.RESERVA, Tipo.AJUSTE):
        return {"comprometido": valor, "executado": ZERO, "alocado": ZERO}
    if transacao.tipo == Tipo.EXECUCAO:
        return {"comprometido": -_valor_total_reservado(transacao.demanda_id), "executado": valor, "alocado": ZERO}
    if transacao.tipo == Tipo.LIBERACAO:
        # A liberação que acompanha uma execução só registra a diferença: o
        # comprometido já saiu por inteiro na execução.
        ja_executada = BudgetTransaction.objects.filter(
            demanda_id=transacao.demanda_id, tipo=Tipo.EXECUCAO,
        ).exists()
        return {"comprometido": ZERO if ja_executada else -valor, "executado": ZERO, "alocado": ZERO}
    return {"comprometido": ZERO, "executado": ZERO, "alocado": valor}


@receiver(post_save, sender=BudgetTransaction)
def auditar_movimentacao_de_saldo(sender, instance, created, **kwargs):
    # A transação é INSERT-only: cada criação é uma movimentação. `demanda_id`
    # guarda o pk da solicitação (DemandRequest), não o da demanda.
    if not created or not (instance.demanda_id or "").isdigit():
        return
    solicitacao = DemandRequest.objects.filter(pk=int(instance.demanda_id)).first()
    if solicitacao is None:
        return

    alocacao = instance.allocation
    efeito = _efeito_na_alocacao(instance)
    posterior = {
        "comprometido": alocacao.valor_comprometido,
        "executado": alocacao.valor_executado,
        "alocado": alocacao.valor_alocado,
    }
    anterior = {campo: posterior[campo] - efeito[campo] for campo in posterior}

    contexto = get_audit_context()
    log_audit(
        user=instance.criado_por,
        acao=f"saldo.{instance.tipo}",
        modulo="sgd",
        entidade=ENTIDADE_MOVIMENTACAO_SALDO,
        entidade_id=instance.pk,
        valores_anteriores={"saldo": {k: str(v) for k, v in anterior.items()}},
        valores_novos={
            "demanda": solicitacao.demanda_id,
            "solicitacao": solicitacao.pk,
            "alocacao": alocacao.pk,
            "tipo": instance.tipo,
            "valor": str(instance.valor),
            "justificativa": instance.justificativa,
            "saldo": {k: str(v) for k, v in posterior.items()},
        },
        _ip=contexto["ip"],
        _user_agent=contexto["user_agent"],
    )
