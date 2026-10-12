import json

import django.db.models.deletion
from django.db import migrations, models

CHAVE = "sgd_mapeamento_tipo_rubrica"

# Duplicado do antigo apps.sgd.services.demand_request.DEFAULT_TIPO_RUBRICA_MAP de
# propósito — migrations não importam código de app que pode mudar.
MAPEAMENTO_PADRAO = {
    "diaria": "diarias",
    "passagem": "passagens-aereas",
    "veiculo": "locacao-veiculo",
    "grafico": "material-grafico",
    "alimentacao": "alimentacao-refeicoes",
    "equipamento": "equipamentos-capital",
}


def migrar_mapeamento(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    BudgetRubrica = apps.get_model("sgp", "BudgetRubrica")
    Mapping = apps.get_model("sgd", "DemandTypeRubricaMapping")

    mapeamento = MAPEAMENTO_PADRAO
    config = SystemConfig.objects.filter(chave=CHAVE).first()
    if config:
        try:
            carregado = json.loads(config.valor)
        except (TypeError, ValueError):
            carregado = None
        if isinstance(carregado, dict):
            mapeamento = carregado

    for tipo, slug in mapeamento.items():
        rubrica = BudgetRubrica.objects.filter(slug=slug).first()
        if rubrica:
            Mapping.objects.get_or_create(tipo=tipo, ativo=True, defaults={"rubrica": rubrica})


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0009_arlo_field_mapping"),
        ("sgp", "0003_arlo_glosa_risk"),
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandTypeRubricaMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(
                    choices=[
                        ("diaria", "Diárias"),
                        ("passagem", "Passagens Aéreas"),
                        ("veiculo", "Locação de Veículo"),
                        ("grafico", "Material Gráfico"),
                        ("alimentacao", "Alimentação"),
                        ("equipamento", "Aquisição de Equipamentos"),
                    ],
                    max_length=20, verbose_name="Tipo de solicitação",
                )),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("rubrica", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="mapeamentos_tipo_sgd",
                    to="sgp.budgetrubrica", verbose_name="Rubrica",
                )),
            ],
            options={
                "verbose_name": "Mapeamento tipo → rubrica",
                "verbose_name_plural": "Mapeamentos tipo → rubrica",
                "ordering": ["tipo", "-ativo", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="demandtyperubricamapping",
            constraint=models.UniqueConstraint(
                condition=models.Q(("ativo", True)), fields=("tipo",), name="uniq_tipo_rubrica_ativo",
            ),
        ),
        migrations.RunPython(migrar_mapeamento, migrations.RunPython.noop),
    ]
