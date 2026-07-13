# Generated manually — choices no modelo

from django.db import migrations, models

from apps.sgp.constants import (
    AGUA_CHOICES,
    COR_RACA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    ESCOLARIDADE_CHOICES,
    ESTADO_CIVIL_CHOICES,
    GENERO_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0003_add_campos_documentacao"),
    ]

    operations = [
        migrations.AddField(model_name="upf", name="genero", field=models.PositiveSmallIntegerField(blank=True, choices=GENERO_CHOICES, null=True, verbose_name="Gênero")),
        migrations.AddField(model_name="upf", name="cor_raca", field=models.PositiveSmallIntegerField(blank=True, choices=COR_RACA_CHOICES, null=True, verbose_name="Cor/Raça")),
        migrations.AddField(model_name="upf", name="estado_civil", field=models.PositiveSmallIntegerField(blank=True, choices=ESTADO_CIVIL_CHOICES, null=True, verbose_name="Estado Civil")),
        migrations.AddField(model_name="upf", name="escolaridade", field=models.PositiveSmallIntegerField(blank=True, choices=ESCOLARIDADE_CHOICES, null=True, verbose_name="Escolaridade")),
        migrations.AddField(model_name="upf", name="dispositivo", field=models.PositiveSmallIntegerField(blank=True, choices=DISPOSITIVO_CHOICES, null=True, verbose_name="Dispositivo")),
        migrations.AddField(model_name="upf", name="pct", field=models.PositiveSmallIntegerField(blank=True, choices=PCT_CHOICES, null=True, verbose_name="PCT")),
        migrations.AddField(model_name="upf", name="posse_terra", field=models.PositiveSmallIntegerField(blank=True, choices=POSSE_TERRA_CHOICES, null=True, verbose_name="Posse da Terra")),
        migrations.AddField(model_name="upf", name="situacao_moradia", field=models.PositiveSmallIntegerField(blank=True, choices=SITUACAO_MORADIA_CHOICES, null=True, verbose_name="Situação da Moradia")),
        migrations.AddField(model_name="upf", name="tipo_moradia", field=models.PositiveSmallIntegerField(blank=True, choices=TIPO_MORADIA_CHOICES, null=True, verbose_name="Tipo de Moradia")),
        migrations.AddField(model_name="upf", name="material_construcao", field=models.PositiveSmallIntegerField(blank=True, choices=MATERIAL_CONSTRUCAO_CHOICES, null=True, verbose_name="Material de Construção")),
        migrations.AddField(model_name="upf", name="num_comodos", field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Número de Cômodos")),
        migrations.AddField(model_name="upf", name="energia", field=models.PositiveSmallIntegerField(blank=True, choices=ENERGIA_CHOICES, null=True, verbose_name="Energia")),
        migrations.AddField(model_name="upf", name="agua", field=models.PositiveSmallIntegerField(blank=True, choices=AGUA_CHOICES, null=True, verbose_name="Água")),
    ]
