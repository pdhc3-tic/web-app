from django.db import migrations

CONFIGURACOES = [
    {
        "chave": "budget_limit_period",
        "valor": "trimestral",
        "tipo": "string",
        "descricao": (
            "Periodicidade dos limites de gasto, uniforme para todo o projeto: "
            "mensal, trimestral, semestral ou vigencia."
        ),
    },
    {
        "chave": "budget_limit_carry_over",
        "valor": "False",
        "tipo": "boolean",
        "descricao": "Se o saldo não utilizado do limite acumula para o período seguinte. Sem acúmulo, ele expira.",
    },
    {
        "chave": "budget_overallocation_allowed",
        "valor": "True",
        "tipo": "boolean",
        "descricao": (
            "Se a soma dos limites individuais de um território pode passar do pool territorial. "
            "O bloqueio efetivo continua sendo o pool."
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
        ("core", "0022_nome_dos_estados_por_extenso"),
    ]

    operations = [
        migrations.RunPython(semear, remover),
    ]
