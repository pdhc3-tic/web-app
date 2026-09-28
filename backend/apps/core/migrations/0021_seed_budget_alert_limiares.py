from django.db import migrations

CONFIGURACOES = [
    {
        "chave": "budget_alert_yellow_pct",
        "valor": "70",
        "tipo": "integer",
        "descricao": (
            "Percentual comprometido a partir do qual o semáforo orçamentário fica amarelo, "
            "em todos os níveis (limite individual, pools e Meta/Submeta/Ação). Editável pelo Super Admin."
        ),
    },
    {
        "chave": "budget_alert_red_pct",
        "valor": "90",
        "tipo": "integer",
        "descricao": (
            "Percentual comprometido a partir do qual o semáforo orçamentário fica vermelho, "
            "em todos os níveis (limite individual, pools e Meta/Submeta/Ação). Editável pelo Super Admin."
        ),
    },
]


def seed_limiares(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for item in CONFIGURACOES:
        SystemConfig.objects.get_or_create(
            chave=item["chave"],
            defaults={"valor": item["valor"], "tipo": item["tipo"], "descricao": item["descricao"]},
        )


def unseed_limiares(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(chave__in=[item["chave"] for item in CONFIGURACOES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.RunPython(seed_limiares, unseed_limiares),
    ]
