from django.db import migrations

CONFIGURACOES = [
    {
        "chave": "budget_subexec_alert_months",
        "valor": "6",
        "tipo": "integer",
        "descricao": "Meses antes do fim da vigência para alertar subexecução.",
    },
    {
        "chave": "budget_subexec_min_pct",
        "valor": "60",
        "tipo": "integer",
        "descricao": "Execução mínima esperada, em percentual, para não disparar o alerta de subexecução.",
    },
    {
        "chave": "budget_transfer_alert_pct",
        "valor": "25",
        "tipo": "integer",
        "descricao": "Volume remanejado de uma rubrica, em percentual do valor aprovado, que dispara o alerta de aditivo.",
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
        ("core", "0023_seed_budget_limites"),
    ]

    operations = [
        migrations.RunPython(semear, remover),
    ]
