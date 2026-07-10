# Generated manually for issue 102.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0003_add_campos_documentacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cultura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('nome_cientifico', models.CharField(blank=True, default='', max_length=160)),
                ('categoria', models.CharField(choices=[('graos', 'Grãos'), ('raizes', 'Raízes'), ('frutas', 'Frutas'), ('hortalicas', 'Hortaliças'), ('leguminosas', 'Leguminosas'), ('oleaginosas', 'Oleaginosas'), ('fibrosas', 'Fibrosas'), ('forrageiras', 'Forrageiras'), ('ornamentais', 'Ornamentais'), ('medicinais', 'Medicinais'), ('outras', 'Outras')], max_length=30)),
                ('ciclo', models.CharField(choices=[('anual', 'Anual'), ('perene', 'Perene'), ('bianual', 'Bianual')], max_length=10)),
                ('ativa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Cultura',
                'verbose_name_plural': 'Culturas',
                'ordering': ['categoria', 'nome'],
                'indexes': [models.Index(fields=['categoria', 'nome'], name='idx_cultura_categoria_nome')],
            },
        ),
        migrations.CreateModel(
            name='EspecieAnimal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('categoria', models.CharField(choices=[('bovino', 'Bovino'), ('suino', 'Suíno'), ('ovino', 'Ovino'), ('caprino', 'Caprino'), ('aves', 'Aves'), ('equino', 'Equino'), ('piscicultura', 'Piscicultura'), ('apicultura', 'Apicultura'), ('outros', 'Outros')], max_length=30)),
                ('ativa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Espécie Animal',
                'verbose_name_plural': 'Espécies Animais',
                'ordering': ['categoria', 'nome'],
                'indexes': [models.Index(fields=['categoria', 'nome'], name='idx_especie_categoria_nome')],
            },
        ),
    ]
