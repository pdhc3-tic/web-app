from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0010_sanea_dados_titularidade_cpf"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="membrofamilia",
            name="unique_titular_por_upf",
        ),
        migrations.RenameField(
            model_name="membrofamilia",
            old_name="data_nasc",
            new_name="data_nascimento",
        ),
        migrations.RenameField(
            model_name="membrofamilia",
            old_name="parentesco",
            new_name="grau_parentesco",
        ),
        migrations.AlterField(
            model_name="membrofamilia",
            name="grau_parentesco",
            field=models.CharField(
                choices=[
                    ("titular", "Titular"),
                    ("conjuge", "Cônjuge"),
                    ("filho", "Filho(a)"),
                    ("enteado", "Enteado(a)"),
                    ("pai", "Pai"),
                    ("mae", "Mãe"),
                    ("irmao", "Irmão(ã)"),
                    ("avo", "Avô(ó)"),
                    ("neto", "Neto(a)"),
                    ("outro", "Outro"),
                ],
                max_length=20,
                verbose_name="Grau de Parentesco",
            ),
        ),
        migrations.AddConstraint(
            model_name="membrofamilia",
            constraint=models.UniqueConstraint(
                condition=models.Q(("grau_parentesco", "titular")),
                fields=("upf",),
                name="unique_titular_por_upf",
            ),
        ),
    ]
