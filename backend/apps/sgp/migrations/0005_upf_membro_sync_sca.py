from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0004_merge_20260728_1916"),
    ]

    operations = [
        migrations.AddField(
            model_name="membrofamilia",
            name="device_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Identificador do dispositivo de origem (sync SCA).",
                max_length=100,
                verbose_name="Device ID",
            ),
        ),
        migrations.AddField(
            model_name="membrofamilia",
            name="uuid_local",
            field=models.UUIDField(
                blank=True,
                null=True,
                unique=True,
                verbose_name="UUID Local",
                help_text="UUID gerado pelo dispositivo para idempotência no sync SCA.",
            ),
        ),
        migrations.AddField(
            model_name="upf",
            name="device_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Identificador do dispositivo de origem (sync SCA).",
                max_length=100,
                verbose_name="Device ID",
            ),
        ),
        migrations.AddField(
            model_name="upf",
            name="uuid_local",
            field=models.UUIDField(
                blank=True,
                null=True,
                unique=True,
                verbose_name="UUID Local",
                help_text="UUID gerado pelo dispositivo para idempotência no sync SCA.",
            ),
        ),
    ]
