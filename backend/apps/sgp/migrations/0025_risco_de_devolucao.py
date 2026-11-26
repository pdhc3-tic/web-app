from django.db import migrations, models

CONFIGURACOES = [
    {
        "chave": "budget_return_risk_alert_months",
        "valor": "12",
        "tipo": "integer",
        "descricao": "Meses antes do fim da vigência a partir dos quais o alerta de risco de devolução é avaliado.",
    },
    {
        "chave": "budget_return_risk_pct",
        "valor": "10",
        "tipo": "integer",
        "descricao": (
            "Saldo remanescente projetado no fim da vigência, em percentual do aprovado, acima do qual "
            "o alerta de risco de devolução dispara."
        ),
    },
]


def semear(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for item in CONFIGURACOES:
        SystemConfig.objects.get_or_create(
            chave=item["chave"],
            defaults={"valor": item["valor"], "tipo": item["tipo"], "descricao": item["descricao"]},
        )


def remover(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(chave__in=[item["chave"] for item in CONFIGURACOES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_perfis_operacionais"),
        ("sgp", "0024_adherence_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="budgetalert",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("semaforo", "Semáforo"),
                    ("subexecucao", "Subexecução"),
                    ("remanejamento_excessivo", "Remanejamento excessivo"),
                    ("risco_devolucao", "Risco de devolução"),
                ],
                max_length=30,
                verbose_name="Tipo",
            ),
        ),
        migrations.RunPython(semear, remover),
    ]
