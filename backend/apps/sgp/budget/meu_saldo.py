"""Quanto o usuário ainda pode solicitar: a leitura dos próprios limites, por rubrica."""
from __future__ import annotations

from apps.core.utils import get_config
from apps.sgp.budget import limites
from apps.sgp.budget.services import _saldo_disponivel, faixa_semaforo, limiares_semaforo, percentual_comprometido
from apps.sgp.models import BudgetPool, BudgetRubrica, BudgetTransaction


def _saldos_do_territorio(territorio_id: int | None) -> dict:
    if territorio_id is None:
        return {}
    pools = BudgetPool.objects.filter(nivel=BudgetPool.Nivel.TERRITORIAL, territorio_id=territorio_id)
    return {pool.rubrica_id: _saldo_disponivel(pool) for pool in pools}


def saldo_por_rubrica(user) -> list[dict]:
    """Uma entrada por rubrica ativa em que o usuário tem limite. Não grava nada: sem linha
    no período, vale a que o padrão do perfil geraria."""
    limiares = limiares_semaforo()
    hoje = limites.hoje()
    acumula = bool(get_config("budget_limit_carry_over", False))
    do_territorio = _saldos_do_territorio(limites.territorio_do_pool(user.pk))

    saldos = []
    for rubrica in BudgetRubrica.objects.filter(ativo=True).order_by("ordem", "pk"):
        limite = limites.limite_efetivo(user.pk, rubrica.pk)
        if limite is None:
            continue
        percentual = percentual_comprometido(limite.valor_comprometido, limite.valor_limite)
        saldos.append({
            "rubrica": rubrica.slug,
            "rubrica_nome": rubrica.nome,
            "limite": limite.valor_limite,
            "comprometido": limite.valor_comprometido,
            "executado": limite.valor_executado,
            "disponivel": limite.saldo_disponivel,
            "semaforo": faixa_semaforo(percentual, limiares),
            "periodo_inicio": limite.periodo_inicio,
            "periodo_fim": limite.periodo_fim,
            "dias_restantes": (limite.periodo_fim - hoje).days,
            "acumula_saldo": acumula,
            "saldo_territorio": do_territorio.get(rubrica.pk),
        })
    return saldos


def extrato(user, rubrica):
    return (
        BudgetTransaction.objects
        .filter(spending_limit__user=user, spending_limit__rubrica=rubrica)
        .select_related("spending_limit")
        .order_by("-criado_em", "-pk")
    )
