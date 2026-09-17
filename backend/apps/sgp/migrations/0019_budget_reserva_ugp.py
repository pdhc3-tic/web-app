from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0018_merge_0016_merge_20260903_1150_0017_seed_rubricas'),
    ]

    operations = [
        migrations.AddField(
            model_name='budgetallocation',
            name='reserva_ugp',
            field=models.BooleanField(
                default=False,
                verbose_name='Reserva Própria da UGP',
                help_text='Só em nível nacional. Uma reserva própria da UGP nunca recebe alocações-filhas.',
            ),
        ),
        migrations.AddConstraint(
            model_name='budgetallocation',
            constraint=models.CheckConstraint(
                condition=models.Q(('reserva_ugp', False)) | models.Q(('nivel', 'nacional')),
                name='ck_budget_allocation_reserva_ugp_so_nacional',
            ),
        ),
    ]
