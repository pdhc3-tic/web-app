from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from apps.sgp.models import WorkPlanAcao


class Command(BaseCommand):
    help = (
        "Reconcilia WorkPlanAcao.quantidade_realizada contra a contagem real de "
        "Atividades com status='concluido' e ativo=True. Por padrão corrige as "
        "divergências encontradas; use --check-only para apenas detectá-las."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-only",
            action="store_true",
            help=(
                "Apenas detecta divergências (levanta erro se houver alguma), "
                "sem corrigir o campo."
            ),
        )

    def handle(self, *args, **options):
        acoes = list(WorkPlanAcao.objects.annotate(
            _esperado=Count(
                "atividades",
                filter=Q(atividades__status="concluido", atividades__ativo=True),
                distinct=True,
            )
        ))

        divergentes = [
            acao for acao in acoes if acao.quantidade_realizada != acao._esperado
        ]

        if options["check_only"]:
            if divergentes:
                divergencias = [
                    f"Ação #{acao.pk} ({acao.numero}): quantidade_realizada="
                    f"{acao.quantidade_realizada} mas a contagem real é {acao._esperado}"
                    for acao in divergentes
                ]
                raise CommandError(
                    f"{len(divergencias)} divergência(s) encontrada(s):\n"
                    + "\n".join(divergencias)
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(acoes)} ação(ões) reconciliada(s) sem divergência."
                )
            )
            return

        if divergentes:
            for acao in divergentes:
                acao.quantidade_realizada = acao._esperado
            WorkPlanAcao.objects.bulk_update(divergentes, ["quantidade_realizada"])
            self.stdout.write(
                self.style.WARNING(
                    f"{len(divergentes)} divergência(s) corrigida(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(acoes)} ação(ões) reconciliada(s) sem divergência."
                )
            )
