from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('sigla', models.CharField(max_length=2, unique=True)),
                ('nome', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'verbose_name': 'Estado',
                'verbose_name_plural': 'Estados',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Territory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('estados', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=2), blank=True, default=list)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('articulador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='territories_articulador', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Território',
                'verbose_name_plural': 'Territórios',
                'ordering': ['nome'],
            },
        ),
        migrations.AddIndex(
            model_name='territory',
            index=models.Index(fields=['ativo'], name='core_territ_ativo_df4832_idx'),
        ),
    ]
