"""Efeito da desativação de um usuário sobre as demandas dele no SGD."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from apps.sgd.models.demand import STATUS_CANCELAVEIS_PELO_SOLICITANTE, Demand
from apps.sgd.services import orcamento as orcamento_service
from apps.sgd.services import workflow as workflow_service

MOTIVO_DESATIVACAO = "Solicitante desativado."


def _demandas_nao_autorizadas(user):
    return Demand.objects.filter(solicitante=user, status__in=STATUS_CANCELAVEIS_PELO_SOLICITANTE)


def impacto_da_desativacao(user) -> dict:
    """O que `cancelar_demandas_do_usuario` faria agora, com o saldo que voltaria ao limite do usuário."""
    demandas = _demandas_nao_autorizadas(user).order_by("pk").prefetch_related("solicitacoes__rubrica")
    itens = []
    rubricas = {}
    por_rubrica = defaultdict(Decimal)
    for demand in demandas:
        ativas = [s for s in demand.solicitacoes.all() if s.reserva_ativa]
        itens.append({
            "id": demand.pk,
            "titulo": demand.titulo,
            "status": demand.status,
            "saldo_liberado": sum((s.valor_no_limite for s in ativas), Decimal("0")),
        })
        for solicitacao in ativas:
            rubricas[solicitacao.rubrica_id] = solicitacao.rubrica.nome
            por_rubrica[solicitacao.rubrica_id] += solicitacao.valor_no_limite
    return {
        "demandas": itens,
        "saldo_por_rubrica": [
            {"rubrica_id": rubrica_id, "rubrica_nome": rubricas[rubrica_id], "valor": por_rubrica[rubrica_id]}
            for rubrica_id in sorted(por_rubrica)
        ],
        "saldo_liberado": sum(por_rubrica.values(), Decimal("0")),
    }


@orcamento_service.com_visao_total
def cancelar_demandas_do_usuario(user, *, por) -> list[Demand]:
    """Só as não autorizadas: uma demanda autorizada depois da leitura faz a
    transação voltar com `TransicaoInvalida`, em vez de ser cancelada. Com visão
    total porque, sem o contexto de quem desativou, o RLS esconderia as demandas e
    o usuário ficaria inativo sem nada cancelado."""
    demandas = list(_demandas_nao_autorizadas(user).select_related("activity__municipio__state", "solicitante"))
    workflow_service.cancelar_pelo_sistema(
        demandas, motivo=MOTIVO_DESATIVACAO, ator=por, status_aceitos=STATUS_CANCELAVEIS_PELO_SOLICITANTE,
        notificacao="cancelamento_por_desativacao",
    )
    return demandas
