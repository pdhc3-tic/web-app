from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_state_territory'),
    ]

    operations = [
        migrations.CreateModel(
            name='Municipality',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=255)),
                ('codigo_ibge', models.CharField(max_length=7, unique=True)),
                ('area_km2', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('pop_total', models.IntegerField(blank=True, null=True)),
                ('pop_rural', models.IntegerField(blank=True, null=True)),
                ('idh', models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True)),
                ('perc_extr_pobres', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('benef_programa_agri_familiar', models.IntegerField(blank=True, null=True)),
                ('estab_agri_familiar', models.IntegerField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('state', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='municipalities', to='core.state')),
                ('territory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='municipalities', to='core.territory')),
            ],
            options={
                'verbose_name': 'Município',
                'verbose_name_plural': 'Municípios',
                'ordering': ['nome'],
            },
        ),
        migrations.AddIndex(
            model_name='municipality',
            index=models.Index(fields=['territory'], name='core_munici_territo_b1bea8_idx'),
        ),
    ]
