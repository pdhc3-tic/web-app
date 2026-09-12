"""Issue #267 — uniformiza soft-delete: ActivityPhoto.ativa -> ativo.

Rename puro de coluna (RenameField preserva os dados). O índice composto
precisa ser recriado apontando para o novo nome de campo; mantém-se o
mesmo nome de índice para minimizar o diff.
"""
import django.db.models.manager
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0029_activitydocument_deleted_at"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="activityphoto",
            name="idx_actphoto_activity_ativa",
        ),
        migrations.RenameField(
            model_name="activityphoto",
            old_name="ativa",
            new_name="ativo",
        ),
        migrations.AlterField(
            model_name="activityphoto",
            name="ativo",
            field=models.BooleanField(default=True, verbose_name="Ativo"),
        ),
        migrations.AddIndex(
            model_name="activityphoto",
            index=models.Index(
                fields=["activity", "ativo"], name="idx_actphoto_activity_ativa"
            ),
        ),
        migrations.AddField(
            model_name="activityphoto",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Desativado em"
            ),
        ),
        migrations.AlterModelOptions(
            name="activityphoto",
            options={
                "base_manager_name": "all_objects",
                "ordering": ["ordem", "criado_em"],
                "verbose_name": "Foto da Atividade",
                "verbose_name_plural": "Fotos da Atividade",
            },
        ),
        migrations.AlterModelManagers(
            name="activityphoto",
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
    ]
