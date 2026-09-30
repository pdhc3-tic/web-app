from django.core.management.base import BaseCommand, CommandError

from apps.sgp.models import WorkPlanAcao
from apps.sgp.models.indicator import FORMA_MANUAL
from apps.sgp.services.apuracao import valores_esperados


class Command(BaseCommand):
    help = (
        "Reconcilia os campos materializados das Ações — quantidade_realizada "
        "(apuração pela forma do Indicador; a forma manual fica de fora) e "
        "valor_executado (demandas concluídas no SGD). Por padrão corrige as "
        "divergências encontradas; use --check-only para apenas detectá-las."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-only",
            action="store_true",
            help=(
                "Apenas detecta divergências (levanta erro se houver alguma), "
                "sem corrigir os campos."
            ),
        )

    def handle(self, *args, **options):
        acoes = valores_esperados()

        divergencias = []
        corrigidas = []
        for acao in acoes:
            campos = []
            if (
                acao.indicador.forma_apuracao != FORMA_MANUAL
                and acao.quantidade_realizada != acao._esperado
            ):
                divergencias.append(
                    f"Ação #{acao.pk} ({acao.numero}): quantidade_realizada="
                    f"{acao.quantidade_realizada} mas a apuração dá {acao._esperado}"
                )
                acao.quantidade_realizada = acao._esperado
                campos.append("quantidade_realizada")
            if acao.valor_executado != acao._valor_esperado:
                divergencias.append(
                    f"Ação #{acao.pk} ({acao.numero}): valor_executado="
                    f"{acao.valor_executado} mas as demandas concluídas somam {acao._valor_esperado}"
                )
                acao.valor_executado = acao._valor_esperado
                campos.append("valor_executado")
            if campos:
                corrigidas.append(acao)

        if options["check_only"]:
            if divergencias:
                raise CommandError(
                    f"{len(divergencias)} divergência(s) encontrada(s):\n"
                    + "\n".join(divergencias)
                )
            self.stdout.write(
                self.style.SUCCESS(f"{len(acoes)} ação(ões) reconciliada(s) sem divergência.")
            )
            return

        if corrigidas:
            WorkPlanAcao.objects.bulk_update(
                corrigidas, ["quantidade_realizada", "valor_executado"]
            )
            self.stdout.write(
                self.style.WARNING(f"{len(divergencias)} divergência(s) corrigida(s).")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"{len(acoes)} ação(ões) reconciliada(s) sem divergência.")
            )
