from django.db import migrations

# §5.3.1 — catálogo fixo das 6 rubricas orçamentárias.
RUBRICAS = [
    {"slug": "diarias", "nome": "Diárias"},
    {"slug": "passagens-aereas", "nome": "Passagens Aéreas"},
    {"slug": "locacao-veiculo", "nome": "Locação de Veículo"},
    {"slug": "alimentacao-refeicoes", "nome": "Alimentação/Refeições"},
    {"slug": "material-grafico", "nome": "Material Gráfico"},
    {"slug": "equipamentos-capital", "nome": "Equipamentos/Capital"},
]


def seed_rubricas(apps, schema_editor):
    BudgetRubrica = apps.get_model("sgp", "BudgetRubrica")
    for ordem, item in enumerate(RUBRICAS, start=1):
        BudgetRubrica.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "nome": item["nome"],
                "ativo": True,
                "ordem": ordem,
            },
        )


def unseed_rubricas(apps, schema_editor):
    BudgetRubrica = apps.get_model("sgp", "BudgetRubrica")
    BudgetRubrica.objects.filter(
        slug__in=[r["slug"] for r in RUBRICAS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0016_budget"),
    ]

    operations = [
        migrations.RunPython(seed_rubricas, unseed_rubricas),
    ]
