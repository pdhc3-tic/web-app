from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from apps.sgp.models import WorkPlanAcao


class Command(BaseCommand):
    help = (
        "Reconcilia WorkPlanAcao.quantidade_realizada contra a contagem real de "
        "Atividades com status='concluido' e ativo=True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Corrige as divergências encontradas em vez de apenas reportá-las.",
        )

    def handle(self, *args, **options):
        acoes = list(WorkPlanAcao.objects.annotate(
            _esperado=Count(
                "atividades",
                filter=Q(atividades__status="concluido", atividades__ativo=True),
                distinct=True,
            )
        ))

        divergencias = []
        corrigidas = []
        for acao in acoes:
            if acao.quantidade_realizada != acao._esperado:
                divergencias.append(
                    f"Ação #{acao.pk} ({acao.numero}): quantidade_realizada="
                    f"{acao.quantidade_realizada} mas a contagem real é {acao._esperado}"
                )
                if options["fix"]:
                    acao.quantidade_realizada = acao._esperado
                    corrigidas.append(acao)

        if options["fix"] and corrigidas:
            WorkPlanAcao.objects.bulk_update(corrigidas, ["quantidade_realizada"])

        if divergencias and not options["fix"]:
            raise CommandError(
                f"{len(divergencias)} divergência(s) encontrada(s):\n" + "\n".join(divergencias)
            )

        if divergencias and options["fix"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(divergencias)} divergência(s) corrigida(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(acoes)} ação(ões) reconciliada(s) sem divergência."
                )
            )
