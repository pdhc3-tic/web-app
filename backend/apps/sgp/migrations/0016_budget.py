import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_power_bi_token'),
        ('sgp', '0015_encripta_campos_sensiveis_membro'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetRubrica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, verbose_name='Nome')),
                ('slug', models.SlugField(max_length=50, unique=True, verbose_name='Slug')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('ordem', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')),
            ],
            options={
                'verbose_name': 'Rubrica Orçamentária',
                'verbose_name_plural': 'Rubricas Orçamentárias',
                'ordering': ['ordem', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='BudgetAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel', models.CharField(choices=[('nacional', 'Nacional'), ('estadual', 'Estadual'), ('territorial', 'Territorial')], max_length=20, verbose_name='Nível')),
                ('valor_alocado', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Alocado (R$)')),
                ('valor_comprometido', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Comprometido (R$)')),
                ('valor_executado', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor Executado (R$)')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('estado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='alocacoes_orcamento', to='core.state', verbose_name='Estado')),
                ('meta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alocacoes_orcamento', to='sgp.workplanmeta', verbose_name='Meta')),
                ('rubrica', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='alocacoes', to='sgp.budgetrubrica', verbose_name='Rubrica')),
                ('territorio', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='alocacoes_orcamento', to='core.territory', verbose_name='Território')),
            ],
            options={
                'verbose_name': 'Alocação Orçamentária',
                'verbose_name_plural': 'Alocações Orçamentárias',
                'ordering': ['meta', 'rubrica', 'nivel'],
            },
        ),
        migrations.CreateModel(
            name='BudgetTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('reserva', 'Reserva'), ('liberacao', 'Liberação'), ('execucao', 'Execução'), ('remanejamento', 'Remanejamento')], max_length=20, verbose_name='Tipo')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Valor (R$)')),
                ('demanda_id', models.CharField(blank=True, default=None, help_text='Referência fraca ao SGD, que ainda não existe.', max_length=64, null=True, verbose_name='ID da Demanda')),
                ('justificativa', models.TextField(blank=True, default='', verbose_name='Justificativa')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('allocation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='sgp.budgetallocation', verbose_name='Alocação')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
            ],
            options={
                'verbose_name': 'Transação Orçamentária',
                'verbose_name_plural': 'Transações Orçamentárias',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='budgetallocation',
            constraint=models.UniqueConstraint(fields=('meta', 'rubrica', 'nivel', 'estado', 'territorio'), name='unique_budget_allocation_combinacao', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='budgetallocation',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('nivel', 'nacional'), ('estado__isnull', True), ('territorio__isnull', True))
                    | models.Q(('nivel', 'estadual'), ('estado__isnull', False), ('territorio__isnull', True))
                    | models.Q(('nivel', 'territorial'), ('territorio__isnull', False))
                ),
                name='ck_budget_allocation_nivel_consistente',
            ),
        ),
        migrations.AddIndex(
            model_name='budgetallocation',
            index=models.Index(fields=['meta', 'rubrica'], name='idx_budgetalloc_meta_rubrica'),
        ),
        migrations.AddIndex(
            model_name='budgetallocation',
            index=models.Index(fields=['nivel', 'territorio'], name='idx_budgetalloc_nivel_territ'),
        ),
    ]
