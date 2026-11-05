from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sgd', '0018_preencher_totais_das_demandas'),
        ('sgp', '0013_converter_limites_individuais'),
    ]

    operations = [
        migrations.DeleteModel(name='DemandIndividualLimit'),
    ]
