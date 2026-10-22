from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0004_budgetincreaserequest_budgettransfer_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='budgetincreaserequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('demanda_id__isnull', False), models.Q(('status__in', ['aprovada', 'aprovada_parcialmente', 'recusada']), _negated=True)),
                fields=('demanda_id', 'rubrica'),
                name='budgetincr_um_pedido_aberto_por_demanda_rubrica',
            ),
        ),
    ]
