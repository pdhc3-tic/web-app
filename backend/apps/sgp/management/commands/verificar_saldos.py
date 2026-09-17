from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.sgp.models import BudgetAllocation, BudgetTransaction

ZERO = Decimal("0")


class Command(BaseCommand):
    help = (
        "Reconcilia valor_comprometido/valor_executado de cada BudgetAllocation "
        "contra a soma das suas BudgetTransaction."
    )

    def handle(self, *args, **options):
        Tipo = BudgetTransaction.Tipo
        alocacoes = list(BudgetAllocation.objects.annotate(
            reserva=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.RESERVA)), ZERO),
            execucao=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.EXECUCAO)), ZERO),
            liberacao=Coalesce(Sum("transactions__valor", filter=Q(transactions__tipo=Tipo.LIBERACAO)), ZERO),
        ))

        divergencias = []
        for alocacao in alocacoes:
            comprometido_esperado = alocacao.reserva - alocacao.execucao - alocacao.liberacao
            executado_esperado = alocacao.execucao

            if alocacao.valor_comprometido != comprometido_esperado:
                divergencias.append(
                    f"Alocação #{alocacao.pk}: valor_comprometido={alocacao.valor_comprometido} "
                    f"mas reserva-execucao-liberacao soma {comprometido_esperado}"
                )
            if alocacao.valor_executado != executado_esperado:
                divergencias.append(
                    f"Alocação #{alocacao.pk}: valor_executado={alocacao.valor_executado} "
                    f"mas execucao soma {executado_esperado}"
                )

        if divergencias:
            raise CommandError(
                f"{len(divergencias)} divergência(s) encontrada(s):\n" + "\n".join(divergencias)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(alocacoes)} alocação(ões) reconciliada(s) sem divergência."
            )
        )
