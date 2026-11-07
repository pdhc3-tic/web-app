from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sca', '0005_alter_conflictlog_estrategia'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncdevice',
            name='espelho_saldo',
            field=models.JSONField(blank=True, default=list, verbose_name='Espelho do saldo'),
        ),
        migrations.AddField(
            model_name='syncdevice',
            name='espelho_saldo_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data do espelho do saldo'),
        ),
    ]
