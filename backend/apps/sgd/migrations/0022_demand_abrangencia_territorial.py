from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_nome_dos_estados_por_extenso'),
        ('sgd', '0021_tipo_vira_fk_do_catalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='demand',
            name='estado_sigla',
            field=models.CharField(
                blank=True, db_index=True, max_length=2, null=True,
                help_text='Estado do solicitante na criação — define o Articulador responsável.',
                verbose_name='Estado (UF) da demanda',
            ),
        ),
        migrations.AddField(
            model_name='demand',
            name='territorio',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='demandas', to='core.territory',
                help_text='Território do solicitante na criação — define o pool territorial.',
                verbose_name='Território da demanda',
            ),
        ),
        migrations.AddIndex(
            model_name='demand',
            index=models.Index(fields=['estado_sigla', 'status'], name='idx_demand_estado_status'),
        ),
    ]
