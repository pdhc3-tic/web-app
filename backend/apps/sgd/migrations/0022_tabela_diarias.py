import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sgd", "0021_tipo_vira_fk_do_catalogo"),
    ]

    operations = [
        migrations.CreateModel(
            name="FaixaDestinoDiaria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150, unique=True, verbose_name="Nome")),
                ("ordem", models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")),
                ("padrao", models.CharField(
                    blank=True, choices=[("capitais", "Capitais sem enquadramento"), ("demais", "Demais localidades")],
                    max_length=10, null=True, unique=True, verbose_name="Recebe os municípios sem enquadramento",
                )),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativa")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Faixa de destino de diária",
                "verbose_name_plural": "Faixas de destino de diária",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.CreateModel(
            name="EnquadramentoFaixaDiaria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_ibge", models.CharField(max_length=7, unique=True, verbose_name="Código IBGE do município")),
                ("nome_referencia", models.CharField(
                    blank=True, default="", max_length=150, verbose_name="Município (referência)",
                )),
                ("faixa", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="enquadramentos",
                    to="sgd.faixadestinodiaria", verbose_name="Faixa",
                )),
            ],
            options={
                "verbose_name": "Enquadramento de município em faixa de diária",
                "verbose_name_plural": "Enquadramentos de municípios em faixas de diária",
                "ordering": ["faixa__ordem", "nome_referencia"],
            },
        ),
        migrations.CreateModel(
            name="TabelaDiaria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("categoria_beneficiario", models.CharField(
                    choices=[("padrao", "Padrão")], default="padrao", max_length=20,
                    verbose_name="Categoria do beneficiário",
                )),
                ("vigencia_inicio", models.DateField(verbose_name="Início da vigência")),
                ("vigencia_fim", models.DateField(blank=True, null=True, verbose_name="Fim da vigência")),
                ("valor", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="Valor da diária (R$)")),
                ("origem", models.CharField(
                    choices=[("federal", "Tabela federal (Decreto 5.992/2006)"), ("fgd", "Valor próprio da FGD")],
                    max_length=10, verbose_name="Origem do valor",
                )),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("criado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="valores_diaria_criados", to=settings.AUTH_USER_MODEL,
                )),
                ("faixa_destino", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="valores",
                    to="sgd.faixadestinodiaria", verbose_name="Faixa de destino",
                )),
            ],
            options={
                "verbose_name": "Valor de diária",
                "verbose_name_plural": "Tabela de diárias",
                "ordering": ["faixa_destino__ordem", "categoria_beneficiario", "-vigencia_inicio"],
                "indexes": [
                    models.Index(
                        fields=["faixa_destino", "categoria_beneficiario", "vigencia_inicio"],
                        name="sgd_tabdiaria_vigencia_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(valor__gt=0), name="sgd_tabela_diaria_valor_positivo"),
                    models.CheckConstraint(
                        condition=models.Q(vigencia_fim__isnull=True)
                        | models.Q(vigencia_fim__gte=models.F("vigencia_inicio")),
                        name="sgd_tabela_diaria_vigencia_coerente",
                    ),
                ],
            },
        ),
    ]
