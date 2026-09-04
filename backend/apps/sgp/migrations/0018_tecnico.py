import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_power_bi_token"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sgp", "0017_seed_rubricas"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tecnico",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("papel", models.CharField(max_length=100, verbose_name="Papel")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                (
                    "osc",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tecnicos",
                        to="core.organization",
                        verbose_name="OSC",
                    ),
                ),
                (
                    "territorio",
                    models.ForeignKey(
                        blank=True,
                        help_text="Se nulo, acesso a todos os territórios.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tecnicos",
                        to="core.territory",
                        verbose_name="Território",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tecnico",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Técnico",
                "verbose_name_plural": "Técnicos",
                "ordering": ["user__nome"],
            },
        ),
        migrations.AddIndex(
            model_name="tecnico",
            index=models.Index(fields=["territorio"], name="idx_tecnico_territorio"),
        ),
        migrations.AddIndex(
            model_name="tecnico",
            index=models.Index(fields=["osc"], name="idx_tecnico_osc"),
        ),
        migrations.AddIndex(
            model_name="tecnico",
            index=models.Index(fields=["ativo"], name="idx_tecnico_ativo"),
        ),
    ]
