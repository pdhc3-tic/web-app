import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0017_merge_20260804_1648"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeedImportRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_file", models.CharField(max_length=255)),
                ("source_sheet", models.CharField(max_length=255)),
                ("source_id", models.CharField(max_length=255)),
                ("object_id", models.PositiveBigIntegerField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source_file", "source_sheet", "source_id"),
                        name="unique_seed_import_source",
                    )
                ],
                "indexes": [
                    models.Index(
                        fields=["content_type", "object_id"],
                        name="idx_seed_import_object",
                    )
                ],
            },
        )
    ]
