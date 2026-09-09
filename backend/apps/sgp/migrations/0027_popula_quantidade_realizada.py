"""
Issue #229 — popula WorkPlanAcao.quantidade_realizada (recém-materializado)
para as Ações já existentes, a partir da contagem real de Atividades com
status='concluido' e ativo=True.
"""
from django.db import migrations
from django.db.models import Count, Q


def popula_quantidade_realizada(apps, schema_editor):
    WorkPlanAcao = apps.get_model("sgp", "WorkPlanAcao")

    acoes = WorkPlanAcao.objects.annotate(
        _real=Count(
            "atividades",
            filter=Q(atividades__status="concluido", atividades__ativo=True),
            distinct=True,
        )
    )

    atualizacoes = list(acoes.iterator())
    for acao in atualizacoes:
        acao.quantidade_realizada = acao._real

    WorkPlanAcao.objects.bulk_update(
        atualizacoes, ["quantidade_realizada"], batch_size=500
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0026_workplanacao_quantidade_realizada"),
    ]

    operations = [
        migrations.RunPython(popula_quantidade_realizada, migrations.RunPython.noop),
    ]
