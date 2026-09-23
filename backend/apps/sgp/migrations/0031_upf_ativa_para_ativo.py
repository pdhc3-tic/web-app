"""Issue #267 — uniformiza soft-delete: UPF.ativa -> ativo.

Rename puro de coluna (RenameField preserva os dados); UPF não tinha
db_index/índice composto dedicado ao campo, então não há índice a recriar.
"""
import django.db.models.manager
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0030_activityphoto_ativa_para_ativo"),
    ]

    operations = [
        migrations.RenameField(
            model_name="upf",
            old_name="ativa",
            new_name="ativo",
        ),
        migrations.AlterField(
            model_name="upf",
            name="ativo",
            field=models.BooleanField(default=True, verbose_name="Ativo"),
        ),
        migrations.AddField(
            model_name="upf",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Desativado em"
            ),
        ),
        migrations.AlterModelOptions(
            name="upf",
            options={
                "base_manager_name": "all_objects",
                "ordering": ["-criado_em"],
                "verbose_name": "UPF",
                "verbose_name_plural": "UPFs",
            },
        ),
        migrations.AlterModelManagers(
            name="upf",
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
    ]
