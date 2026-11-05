from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0008_preencher_escopo_das_transferencias'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetPool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel', models.CharField(choices=[('nacional', 'Nacional'), ('estadual', 'Estadual'), ('territorial', 'Territorial')], max_length=20, verbose_name='Nível')),
                ('valor_alocado', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Alocado (R$)')),
                ('valor_comprometido', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Comprometido (R$)')),
                ('valor_executado', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Executado (R$)')),
                ('reserva_ugp', models.BooleanField(default=False, help_text='Só em nível nacional. Uma reserva própria da UGP nunca recebe pools-filhos.', verbose_name='Reserva Própria da UGP')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('estado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pools_orcamento', to='core.state', verbose_name='Estado')),
                ('rubrica', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pools', to='sgp.budgetrubrica', verbose_name='Rubrica')),
                ('territorio', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pools_orcamento', to='core.territory', verbose_name='Território')),
            ],
            options={
                'verbose_name': 'Pool Orçamentário',
                'verbose_name_plural': 'Pools Orçamentários',
                'ordering': ['rubrica', 'nivel'],
                'indexes': [models.Index(fields=['nivel', 'territorio'], name='idx_budgetpool_nivel_territ')],
                'constraints': [
                    models.UniqueConstraint(fields=('rubrica', 'nivel', 'estado', 'territorio'), name='unique_budget_pool_combinacao', nulls_distinct=False),
                    models.CheckConstraint(condition=models.Q(models.Q(('estado__isnull', True), ('nivel', 'nacional'), ('territorio__isnull', True)), models.Q(('estado__isnull', False), ('nivel', 'estadual'), ('territorio__isnull', True)), models.Q(('nivel', 'territorial'), ('territorio__isnull', False)), _connector='OR'), name='ck_budget_pool_nivel_consistente'),
                    models.CheckConstraint(condition=models.Q(('reserva_ugp', False), ('nivel', 'nacional'), _connector='OR'), name='ck_budget_pool_reserva_ugp_so_nacional'),
                ],
            },
        ),
        migrations.AddField(
            model_name='budgettransaction',
            name='pool',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='sgp.budgetpool', verbose_name='Pool'),
        ),
        migrations.AddField(
            model_name='budgettransaction',
            name='activity',
            field=models.ForeignKey(blank=True, help_text='Liga o executado à Meta, pela cadeia Atividade → Ação → Meta.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transacoes_orcamento', to='sgp.activity', verbose_name='Atividade'),
        ),
        migrations.AddField(
            model_name='budgettransfer',
            name='pool_origem',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_saida', to='sgp.budgetpool', verbose_name='Pool de origem'),
        ),
        migrations.AddField(
            model_name='budgettransfer',
            name='pool_destino',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_entrada', to='sgp.budgetpool', verbose_name='Pool de destino'),
        ),
        # Nuláveis para a reversão recriar as colunas antes de preencher as alocações.
        migrations.AlterField(
            model_name='budgettransaction',
            name='allocation',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='sgp.budgetallocation', verbose_name='Alocação'),
        ),
        migrations.AlterField(
            model_name='budgettransfer',
            name='allocation_origem',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_saida', to='sgp.budgetallocation', verbose_name='Alocação de origem'),
        ),
        migrations.AlterField(
            model_name='budgettransfer',
            name='allocation_destino',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transferencias_de_entrada', to='sgp.budgetallocation', verbose_name='Alocação de destino'),
        ),
    ]
