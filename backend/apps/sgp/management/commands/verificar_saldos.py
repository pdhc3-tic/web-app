from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.sgd.services.reconciliacao import divergencias_dos_limites, divergencias_dos_totais
from apps.sgp.models import BudgetPool, BudgetTransaction

ZERO = Decimal("0")


class Command(BaseCommand):
    help = (
        "Reconcilia valor_comprometido/valor_executado de cada BudgetPool "
        "contra a soma das suas BudgetTransaction, o comprometido de cada limite "
        "individual do SGD contra as reservas ativas das solicitações e os totais de "
        "cada demanda contra a soma das solicitações."
    )

    def handle(self, *args, **options):
        Tipo = BudgetTransaction.Tipo
        pools = list(BudgetPool.objects.annotate(
            reserva=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.RESERVA)), ZERO),
            ajuste=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.AJUSTE)), ZERO),
            execucao=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.EXECUCAO)), ZERO),
            liberacao=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.LIBERACAO)), ZERO),
        ))

        divergencias = []
        for pool in pools:
            # `ajuste` soma os deltas de `ajustar_reserva` (SGD) — sem somar
            # aqui, um pool com ajuste aplicado sempre divergiria.
            comprometido_esperado = pool.reserva + pool.ajuste - pool.execucao - pool.liberacao
            executado_esperado = pool.execucao

            if pool.valor_comprometido != comprometido_esperado:
                divergencias.append(
                    f"Pool #{pool.pk}: valor_comprometido={pool.valor_comprometido} "
                    f"mas reserva-execucao-liberacao soma {comprometido_esperado}"
                )
            if pool.valor_executado != executado_esperado:
                divergencias.append(
                    f"Pool #{pool.pk}: valor_executado={pool.valor_executado} "
                    f"mas execucao soma {executado_esperado}"
                )

        divergencias += divergencias_dos_limites()
        divergencias += divergencias_dos_totais()

        if divergencias:
            raise CommandError(
                f"{len(divergencias)} divergência(s) encontrada(s):\n" + "\n".join(divergencias)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(pools)} pool(s) reconciliado(s) sem divergência."
            )
        )
