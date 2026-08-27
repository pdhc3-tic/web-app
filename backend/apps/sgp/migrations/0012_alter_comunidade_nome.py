from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0006_merge_20260804_1648"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comunidade",
            name="nome",
            field=models.CharField(max_length=255),
        ),
    ]
