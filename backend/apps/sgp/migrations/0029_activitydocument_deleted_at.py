"""Issue #267 — uniformiza soft-delete: ActivityDocument herda de SoftDeleteModel."""
import django.db.models.manager
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0028_activity_deleted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitydocument",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Desativado em"
            ),
        ),
        migrations.AlterModelOptions(
            name="activitydocument",
            options={
                "base_manager_name": "all_objects",
                "ordering": ["-criado_em"],
                "verbose_name": "Documento da Atividade",
                "verbose_name_plural": "Documentos da Atividade",
            },
        ),
        migrations.AlterModelManagers(
            name="activitydocument",
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
    ]
