"""Remanejamento de saldo estadual ou nacional para o pool territorial do solicitante.

Um serviço só para as duas formas que o SGD tem de cobrir saldo com outro nível: a
decisão do recurso extra, que eleva o limite individual, e o excedente pontual que a
UGP autoriza na própria demanda (remanejamento emergencial), que não eleva.

Ordem de lock: `DemandIndividualLimit` → `BudgetAllocation` (em ordem de pk), a de
`backend/docs/orcamento.md`.
"""

from __future__ import annotations

from decimal import Decimal

from apps.core.signals.audit import get_audit_context
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services import orcamento as orcamento_service
from apps.sgp.models import BudgetAllocation, BudgetTransfer

ZERO = Decimal("0")

ENTIDADE_REMANEJAMENTO = "BudgetTransfer"

Escopo = BudgetTransfer.Escopo


def exigir_origem_acima_do_territorio(origem: BudgetAllocation) -> None:
    if origem.nivel not in (orcamento_service.Nivel.ESTADUAL, orcamento_service.Nivel.NACIONAL):
        raise RegraDeNegocio("O remanejamento só pode vir de saldo estadual ou nacional.", campo="origem_allocation")


def remanejar_para_pool(*, origem: BudgetAllocation, destino: BudgetAllocation, valor: Decimal, motivo: str,
                        usuario, escopo: str, increase_request=None, demanda_id: str | None = None,
                        solicitacao_id: str | None = None) -> BudgetTransfer:
    """`origem` e `destino` já travados por quem chama, que também já decidiu `valor`."""
    origem_antes, destino_antes = orcamento_service.saldo_do_pool(origem), orcamento_service.saldo_do_pool(destino)
    orcamento_service.remanejar(origem=origem, destino=destino, valor=valor, usuario=usuario, justificativa=motivo)
    origem.refresh_from_db()
    destino.refresh_from_db()

    transferencia = BudgetTransfer.objects.create(
        tipo=BudgetTransfer.Tipo.ENTRE_NIVEIS, escopo=escopo, allocation_origem=origem, allocation_destino=destino,
        valor=valor, motivo=motivo,
        saldo_origem_antes=origem_antes, saldo_origem_depois=orcamento_service.saldo_do_pool(origem),
        saldo_destino_antes=destino_antes, saldo_destino_depois=orcamento_service.saldo_do_pool(destino),
        aprovado_por=usuario, ip=get_audit_context()["ip"], increase_request=increase_request,
        demanda_id=demanda_id, solicitacao_id=solicitacao_id,
    )
    auditoria_service.registrar_evento(
        acao="remanejamento.efetivado", entidade=ENTIDADE_REMANEJAMENTO, entidade_id=transferencia.pk,
        usuario=usuario,
        anteriores={"saldo_origem": str(origem_antes), "saldo_destino": str(destino_antes)},
        novos={
            "valor": str(valor), "escopo": escopo,
            "pedido": increase_request.pk if increase_request is not None else None,
            "demanda": demanda_id, "solicitacao": solicitacao_id,
            "origem": origem.pk, "destino": destino.pk,
            "saldo_origem": str(transferencia.saldo_origem_depois),
            "saldo_destino": str(transferencia.saldo_destino_depois),
        },
    )
    destinatarios = {
        u.pk: u for alocacao in (origem, destino)
        for u in balance_service._destinatarios_saldo_territorial(
            nivel=alocacao.nivel, estado_sigla=alocacao.estado.sigla if alocacao.estado else None,
            territorio=alocacao.territorio,
        )
    }
    notifications_service.notificar_remanejamento_efetivado(transferencia, list(destinatarios.values()))
    return transferencia


def cobrir_excedente(solicitacao, novo_valor: Decimal, *, origem: BudgetAllocation, justificativa: str,
                     usuario) -> tuple[Decimal, BudgetTransfer | None]:
    """Remaneja de `origem` o que o aumento da reserva para `novo_valor` passa do limite
    individual ou do pool territorial (o maior dos dois). Devolve a parte acima do
    limite individual, que `ajustar_duas_travas` deixa fora do limite, e a
    transferência.

    Sem nada acima do limite nem do pool, não remaneja: (zero, None)."""
    exigir_origem_acima_do_territorio(origem)
    if origem.rubrica_id != solicitacao.rubrica_id:
        raise RegraDeNegocio(
            "A alocação de origem precisa ser da mesma rubrica da solicitação que excede.",
            campo="origem_allocation",
        )
    solicitante = solicitacao.demanda.solicitante
    limite = balance_service._travar_limite(solicitante_id=solicitante.pk, rubrica_id=solicitacao.rubrica_id)
    balance_service.reler_reserva(solicitacao)
    aumento = novo_valor - solicitacao.valor_reservado
    if limite is None or not solicitacao.reserva_ativa or aumento <= ZERO:
        return ZERO, None

    # Saldo negativo vem de excedente autorizado antes deste fluxo: não cobre nada.
    acima_do_limite = max(aumento - max(limite.saldo_disponivel, ZERO), ZERO)
    # O pool da reserva, que é o que o ajuste move, e não o do perfil atual do
    # solicitante, que pode ter mudado depois da submissão.
    destino = orcamento_service.pool_da_reserva(solicitacao)
    if destino is None:
        raise RegraDeNegocio(f"A solicitação #{solicitacao.pk} não tem reserva no pool territorial.")
    travadas = orcamento_service.travar_pools({origem.pk, destino.pk})
    origem, destino = travadas[origem.pk], travadas[destino.pk]
    acima_do_pool = max(aumento - orcamento_service.saldo_do_pool(destino), ZERO)
    valor = max(acima_do_limite, acima_do_pool)
    if valor == ZERO:
        return ZERO, None

    transferencia = remanejar_para_pool(
        origem=origem, destino=destino, valor=valor, usuario=usuario, escopo=Escopo.PONTUAL,
        motivo=f"Excedente autorizado na demanda #{solicitacao.demanda_id}: {justificativa}",
        demanda_id=str(solicitacao.demanda_id), solicitacao_id=str(solicitacao.pk),
    )
    return acima_do_limite, transferencia
