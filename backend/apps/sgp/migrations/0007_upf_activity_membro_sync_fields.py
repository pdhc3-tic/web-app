from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0006_merge_20260804_1648"),
    ]

    operations = [
        migrations.AddField(
            model_name="upf",
            name="ultima_origem",
            field=models.CharField(
                choices=[("sca", "SCA"), ("web", "Web")],
                default="web",
                help_text="Indica se a última alteração partiu do app SCA ou da plataforma Web.",
                max_length=10,
                verbose_name="Última Origem",
            ),
        ),
        migrations.AddField(
            model_name="upf",
            name="ultimo_sync_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp da última sincronização bem-sucedida via SCA.",
                null=True,
                verbose_name="Último Sync SCA",
            ),
        ),
        migrations.AddField(
            model_name="membrofamilia",
            name="ultima_origem",
            field=models.CharField(
                choices=[("sca", "SCA"), ("web", "Web")],
                default="web",
                help_text="Indica se a última alteração partiu do app SCA ou da plataforma Web.",
                max_length=10,
                verbose_name="Última Origem",
            ),
        ),
        migrations.AddField(
            model_name="membrofamilia",
            name="ultimo_sync_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp da última sincronização bem-sucedida via SCA.",
                null=True,
                verbose_name="Último Sync SCA",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="ultima_origem",
            field=models.CharField(
                choices=[("sca", "SCA"), ("web", "Web")],
                default="web",
                help_text="Indica se a última alteração partiu do app SCA ou da plataforma Web.",
                max_length=10,
                verbose_name="Última Origem",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="ultimo_sync_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp da última sincronização bem-sucedida via SCA.",
                null=True,
                verbose_name="Último Sync SCA",
            ),
        ),
    ]
