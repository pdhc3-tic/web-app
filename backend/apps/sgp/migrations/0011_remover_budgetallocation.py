from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0010_preencher_budgetpool'),
    ]

    operations = [
        migrations.RemoveField(model_name='budgettransaction', name='allocation'),
        migrations.RemoveField(model_name='budgettransfer', name='allocation_origem'),
        migrations.RemoveField(model_name='budgettransfer', name='allocation_destino'),
        migrations.DeleteModel(name='BudgetAllocation'),
        migrations.AlterField(
            model_name='budgettransaction',
            name='pool',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='sgp.budgetpool', verbose_name='Pool'),
        ),
        migrations.AlterField(
            model_name='budgettransfer',
            name='pool_origem',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_saida', to='sgp.budgetpool', verbose_name='Pool de origem'),
        ),
        migrations.AlterField(
            model_name='budgettransfer',
            name='pool_destino',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_entrada', to='sgp.budgetpool', verbose_name='Pool de destino'),
        ),
        migrations.AlterField(
            model_name='budgettransfer',
            name='escopo',
            field=models.CharField(blank=True, choices=[('pontual', 'Pontual (excedente autorizado na demanda)'), ('elevacao_limite', 'Elevação do limite individual (recurso extra)')], default='', help_text='Em branco no remanejamento feito direto entre pools, sem demanda envolvida.', max_length=20, verbose_name='Escopo'),
        ),
    ]
