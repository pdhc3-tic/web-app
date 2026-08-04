# Generated for issue 103.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0002_seed_catalogos"),
    ]

    operations = [
        migrations.CreateModel(
            name="Production",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("agricola", "Agrícola"), ("pecuaria", "Pecuária"), ("outra", "Outra")], max_length=20, verbose_name="Tipo")),
                ("area_ha", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Área (ha)")),
                ("producao_estimada", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Produção Estimada")),
                ("unidade_producao", models.CharField(blank=True, max_length=50, null=True, verbose_name="Unidade de Produção")),
                ("sementes_crioulas", models.BooleanField(default=False, verbose_name="Sementes Crioulas")),
                ("n_matrizes", models.PositiveIntegerField(blank=True, null=True, verbose_name="Número de Matrizes")),
                ("n_reprodutores", models.PositiveIntegerField(blank=True, null=True, verbose_name="Número de Reprodutores")),
                ("n_jovens", models.PositiveIntegerField(blank=True, null=True, verbose_name="Número de Jovens")),
                ("area_pastejo_ha", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Área de Pastejo (ha)")),
                ("sistema_criacao", models.CharField(blank=True, choices=[("extensivo", "Extensivo"), ("semi_intensivo", "Semi-intensivo"), ("intensivo", "Intensivo")], max_length=20, null=True, verbose_name="Sistema de Criação")),
                ("tipo_outra", models.CharField(blank=True, choices=[("artesanato", "Artesanato"), ("beneficiamento", "Beneficiamento"), ("extrativismo", "Extrativismo"), ("outro", "Outro")], max_length=20, null=True, verbose_name="Tipo de Outra Atividade")),
                ("descricao_outra", models.TextField(blank=True, null=True, verbose_name="Descrição da Outra Atividade")),
                ("quantidade_produzida", models.CharField(blank=True, max_length=120, null=True, verbose_name="Quantidade Produzida")),
                ("renda_estimada_mensal", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Renda Estimada Mensal")),
                ("custo_anual", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Custo Anual")),
                ("observacoes", models.TextField(blank=True, null=True, verbose_name="Observações")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("cultura", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="producoes", to="sgp.cultura", verbose_name="Cultura")),
                ("especie", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="producoes", to="sgp.especieanimal", verbose_name="Espécie Animal")),
                ("upf", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="producoes", to="sgp.upf", verbose_name="UPF")),
            ],
            options={
                "verbose_name": "Produção",
                "verbose_name_plural": "Produções",
                "ordering": ["-criado_em"],
                "indexes": [models.Index(fields=["upf"], name="idx_production_upf")],
            },
        ),
    ]
