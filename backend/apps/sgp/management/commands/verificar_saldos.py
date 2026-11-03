from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.sgd.services.reconciliacao import divergencias_dos_limites, divergencias_dos_totais
from apps.sgp.budget.rls import visao_total
from apps.sgp.models import BudgetPool, BudgetTransaction, SpendingLimit

ZERO = Decimal("0")
Tipo = BudgetTransaction.Tipo


def _com_somas_do_ledger(queryset, campo_no_ledger: str):
    def soma(tipo):
        return Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=tipo)), ZERO)

    ultimo = BudgetTransaction.objects.filter(**{campo_no_ledger: OuterRef("pk")}).order_by("-pk")
    return queryset.annotate(
        reserva=soma(Tipo.RESERVA), ajuste=soma(Tipo.AJUSTE), execucao=soma(Tipo.EXECUCAO), liberacao=soma(Tipo.LIBERACAO),
        ultimo_saldo=Subquery(ultimo.values("saldo_posterior")[:1]),
    )


def _divergencias(rotulo: str, linhas, saldo_de) -> list[str]:
    divergencias = []
    for linha in linhas:
        # `ajuste` soma os deltas de `ajustar_reserva` (SGD) — sem somar
        # aqui, uma linha com ajuste aplicado sempre divergiria.
        comprometido_esperado = linha.reserva + linha.ajuste - linha.execucao - linha.liberacao
        if linha.valor_comprometido != comprometido_esperado:
            divergencias.append(
                f"{rotulo} #{linha.pk}: valor_comprometido={linha.valor_comprometido} "
                f"mas reserva-execucao-liberacao soma {comprometido_esperado}"
            )
        if linha.valor_executado != linha.execucao:
            divergencias.append(
                f"{rotulo} #{linha.pk}: valor_executado={linha.valor_executado} "
                f"mas execucao soma {linha.execucao}"
            )
        saldo = saldo_de(linha)
        if linha.ultimo_saldo is not None and linha.ultimo_saldo != saldo:
            divergencias.append(
                f"{rotulo} #{linha.pk}: saldo disponível={saldo} "
                f"mas o saldo_posterior da última transação é {linha.ultimo_saldo}"
            )
    return divergencias


class Command(BaseCommand):
    help = (
        "Reconcilia cada BudgetPool e cada SpendingLimit contra o ledger (somas por tipo e "
        "saldo_posterior da última transação), o comprometido dos limites individuais contra as "
        "reservas ativas das solicitações e os totais de cada demanda contra a soma das solicitações."
    )

    def handle(self, *args, **options):
        # O comando não passa pelo middleware que define o papel da sessão para o RLS.
        with visao_total():
            pools = list(_com_somas_do_ledger(BudgetPool.objects.all(), "pool"))
            limites = list(_com_somas_do_ledger(
                SpendingLimit.objects.filter(escopo=SpendingLimit.Escopo.INDIVIDUAL), "spending_limit",
            ))
            divergencias = _divergencias(
                "Pool", pools, lambda p: p.valor_alocado - p.valor_comprometido - p.valor_executado,
            )
            divergencias += _divergencias("Limite", limites, lambda limite: limite.saldo_disponivel)
            divergencias += divergencias_dos_limites()
            divergencias += divergencias_dos_totais()

        if divergencias:
            raise CommandError(
                f"{len(divergencias)} divergência(s) encontrada(s):\n" + "\n".join(divergencias)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(pools)} pool(s) e {len(limites)} limite(s) reconciliado(s) sem divergência."
            )
        )
