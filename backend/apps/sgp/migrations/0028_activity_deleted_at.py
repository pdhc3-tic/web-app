"""Issue #267 — uniformiza soft-delete: Activity herda de SoftDeleteModel."""
import django.db.models.manager
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0027_popula_quantidade_realizada"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Desativado em"
            ),
        ),
        migrations.AlterModelOptions(
            name="activity",
            options={
                "base_manager_name": "all_objects",
                "ordering": ["-data_inicio", "-criado_em"],
                "verbose_name": "Atividade",
                "verbose_name_plural": "Atividades",
            },
        ),
        migrations.AlterModelManagers(
            name="activity",
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
    ]
