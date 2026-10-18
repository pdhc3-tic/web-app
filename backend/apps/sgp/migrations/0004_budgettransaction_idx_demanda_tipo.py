from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0003_arlo_glosa_risk'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='budgettransaction',
            index=models.Index(fields=['demanda_id', 'tipo'], name='idx_budgettx_demanda_tipo'),
        ),
    ]
