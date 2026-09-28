import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.sgp.models.workplan


class Migration(migrations.Migration):
    """Primeiro de três passos: cria Indicador e Submeta e liga a Ação a eles
    com FKs ainda nuláveis, para que a migration seguinte preencha os dados
    existentes antes de a 0035 torná-las obrigatórias."""

    dependencies = [
        ("sgp", "0034_exportjob_enfileirado_em"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Indicator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(help_text="Identificador curto e estável (ex: IND-OFI).", max_length=20, unique=True, verbose_name="Código")),
                ("nome", models.CharField(max_length=255, verbose_name="Nome")),
                ("unidade_medida", models.CharField(choices=[("unidade", "Unidade"), ("familia", "Família"), ("pessoa", "Pessoa"), ("evento", "Evento"), ("plano", "Plano"), ("relatorio", "Relatório"), ("hectare", "Hectare"), ("outro", "Outro")], max_length=20, verbose_name="Unidade de medida")),
                ("forma_apuracao", models.CharField(choices=[("contagem_atividades", "Contagem de atividades concluídas"), ("soma_ufpas", "Soma de UFPAs vinculadas"), ("soma_participantes", "Soma de participantes"), ("manual", "Lançamento manual pela UGP")], max_length=20, verbose_name="Forma de apuração")),
                ("categoria", models.CharField(blank=True, choices=[("formacao", "Formação"), ("assistencia_tecnica", "Assistência técnica"), ("estruturacao_produtiva", "Estruturação produtiva"), ("gestao", "Gestão"), ("outro", "Outro")], default="", max_length=30, verbose_name="Categoria")),
                ("ods_ids", models.JSONField(blank=True, default=list, help_text="Lista de IDs dos Objetivos de Desenvolvimento Sustentável (1–17).", verbose_name="ODS")),
                ("desagregacoes", models.JSONField(blank=True, default=list, help_text="Recortes que o relatório do Indicador deve produzir.", verbose_name="Desagregação exigida")),
                ("ativo", models.BooleanField(default=True, help_text="Inativo não pode ser vinculado a novas Ações, mas preserva o histórico.", verbose_name="Ativo")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Criado por")),
            ],
            options={
                "verbose_name": "Indicador",
                "verbose_name_plural": "Indicadores",
                "ordering": ["codigo"],
                "indexes": [models.Index(fields=["ativo"], name="idx_indicator_ativo")],
            },
        ),
        migrations.CreateModel(
            name="WorkPlanSubmeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(help_text="Numeração X.Y, com X igual ao número da Meta.", max_length=10, validators=[apps.sgp.models.workplan.validate_numero_submeta], verbose_name="Número")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("descricao", models.TextField(blank=True, default="", verbose_name="Descrição")),
                ("data_inicio", models.DateField(verbose_name="Data de Início")),
                ("data_fim", models.DateField(verbose_name="Data de Término")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Criado por")),
                ("meta", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submetas", to="sgp.workplanmeta", verbose_name="Meta")),
                ("responsavel", models.ForeignKey(blank=True, help_text="Usuário da UGP que acompanha a Submeta.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submetas_responsavel", to=settings.AUTH_USER_MODEL, verbose_name="Responsável")),
            ],
            options={
                "verbose_name": "Submeta do Plano de Trabalho",
                "verbose_name_plural": "Submetas do Plano de Trabalho",
                "ordering": ["meta", "numero"],
                "indexes": [models.Index(fields=["meta"], name="idx_wpsubmeta_meta")],
                "constraints": [models.UniqueConstraint(fields=("meta", "numero"), name="unique_numero_submeta_por_meta")],
            },
        ),
        migrations.AddField(
            model_name="workplanacao",
            name="submeta",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="acoes", to="sgp.workplansubmeta", verbose_name="Submeta"),
        ),
        # O tamanho novo do número entra antes dos dados: no rollback, a coluna
        # só volta a encolher depois de a 0034 converter X.Y.Z de volta em X.Y.
        migrations.AlterField(
            model_name="workplanacao",
            name="numero",
            field=models.CharField(help_text="Numeração X.Y.Z, com X.Y igual ao número da Submeta.", max_length=12, validators=[apps.sgp.models.workplan.validate_numero_acao], verbose_name="Número"),
        ),
        # Nulável aqui para a 0035 poder removê-la e, no rollback, recriá-la
        # vazia até a 0034 reverter os valores; só esta migration volta a
        # exigir o campo, quando já está preenchido.
        migrations.AlterField(
            model_name="workplanacao",
            name="tipo_unidade",
            field=models.PositiveSmallIntegerField(choices=[(1, "Seminário"), (2, "Oficina"), (3, "Curso / Capacitação"), (4, "Plano"), (5, "Relatório de pesquisas"), (6, "Intercâmbio"), (7, "Conteúdo audiovisual"), (8, "Visita técnica"), (9, "Encontro / Reunião"), (10, "Unidade implementada"), (11, "Família atendida"), (12, "Outro")], null=True, verbose_name="Tipo de Unidade"),
        ),
        migrations.AddField(
            model_name="workplanacao",
            name="indicador",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="acoes", to="sgp.indicator", verbose_name="Indicador"),
        ),
    ]
