from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sgd', '0014_preencher_estado_da_reserva'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='demandindividuallimit',
            constraint=models.CheckConstraint(condition=models.Q(('valor_comprometido__gte', 0)), name='ck_demandindividuallimit_comprometido_nao_negativo'),
        ),
        migrations.AddConstraint(
            model_name='demandindividuallimit',
            constraint=models.CheckConstraint(condition=models.Q(('valor_executado__gte', 0)), name='ck_demandindividuallimit_executado_nao_negativo'),
        ),
        migrations.AddConstraint(
            model_name='demandrequest',
            constraint=models.CheckConstraint(condition=models.Q(('valor_reservado__gte', 0)), name='ck_demandrequest_valor_reservado_nao_negativo'),
        ),
        migrations.AddConstraint(
            model_name='demandrequest',
            constraint=models.CheckConstraint(condition=models.Q(('valor_executado__isnull', True), ('valor_executado__gte', 0), _connector='OR'), name='ck_demandrequest_valor_executado_nao_negativo'),
        ),
    ]
