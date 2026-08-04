from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sgp", "0004_merge_20260728_1916"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activity",
            name="data_inicio",
            field=models.DateTimeField(verbose_name="Data de Início"),
        ),
        migrations.AlterField(
            model_name="activity",
            name="data_fim",
            field=models.DateTimeField(verbose_name="Data de Fim"),
        ),
        migrations.AddField(
            model_name="activity",
            name="google_calendar_event_id",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="ID do Evento Google Calendar",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="google_calendar_sync_status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("ok", "OK"),
                    ("erro", "Erro"),
                ],
                default="ok",
                max_length=20,
                verbose_name="Status de Sync Google Calendar",
            ),
        ),
    ]
