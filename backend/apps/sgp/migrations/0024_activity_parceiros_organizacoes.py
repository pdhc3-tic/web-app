from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_power_bi_token"),
        ("sgp", "0023_alter_tecnico_id"),
    ]

    operations = [
        migrations.RenameField(
            model_name="activity",
            old_name="parceiros",
            new_name="parceiros_livres",
        ),
        migrations.AlterField(
            model_name="activity",
            name="parceiros_livres",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Parceiros em texto livre que não corresponderam a nenhuma Organization cadastrada.",
                verbose_name="Parceiros (texto livre)",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="parceiros_organizacoes",
            field=models.ManyToManyField(
                blank=True,
                related_name="atividades",
                to="core.organization",
                verbose_name="Organizações Parceiras",
            ),
        ),
    ]
