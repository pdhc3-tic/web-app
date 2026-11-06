import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preencher_origem_e_atividade(apps, schema_editor):
    GlosaRisk = apps.get_model("sgp", "GlosaRisk")
    Demand = apps.get_model("sgd", "Demand")
    riscos = list(GlosaRisk.objects.all())
    atividades = dict(
        Demand.objects.filter(pk__in={int(risco.demanda_id) for risco in riscos}).values_list("pk", "activity_id")
    )
    for risco in riscos:
        risco.entidade_id = risco.demanda_id
        risco.activity_id = atividades.get(int(risco.demanda_id))
    GlosaRisk.objects.bulk_update(riscos, ["entidade_id", "activity"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sgd", "0021_tipo_vira_fk_do_catalogo"),
        ("sgp", "0017_ajustes_de_pool_e_limite"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="glosarisk", name="uniq_glosarisk_solicitacao_import"),
        migrations.RenameField(model_name="glosarisk", old_name="excedente", new_name="valor_exposto"),
        migrations.RenameField(model_name="glosarisk", old_name="criado_em", new_name="detectado_em"),
        migrations.AlterModelOptions(
            name="glosarisk",
            options={
                "ordering": ["-detectado_em"],
                "verbose_name": "Risco de Glosa",
                "verbose_name_plural": "Riscos de Glosa",
            },
        ),
        migrations.AlterField(
            model_name="glosarisk",
            name="valor_exposto",
            field=models.DecimalField(decimal_places=2, max_digits=14, verbose_name="Valor exposto (R$)"),
        ),
        migrations.AlterField(
            model_name="glosarisk",
            name="detectado_em",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Detectado em"),
        ),
        migrations.AlterField(
            model_name="glosarisk",
            name="demand_request_id",
            field=models.CharField(
                blank=True, default="", help_text="Referência fraca ao DemandRequest que recebeu o pagamento.",
                max_length=64, verbose_name="ID da Solicitação",
            ),
        ),
        migrations.AlterField(
            model_name="glosarisk",
            name="valor_autorizado",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="Valor autorizado (R$)",
            ),
        ),
        migrations.AlterField(
            model_name="glosarisk",
            name="valor_pago",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="Valor pago (R$)",
            ),
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="tipo_situacao",
            field=models.CharField(
                choices=[
                    ("pago_acima_autorizado", "Pago acima do autorizado"),
                    ("demanda_sem_evidencia", "Demanda executada sem evidência"),
                ],
                default="pago_acima_autorizado", max_length=30, verbose_name="Situação",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="severidade",
            field=models.CharField(
                choices=[("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")],
                default="alta", max_length=5, verbose_name="Severidade",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="entidade",
            field=models.CharField(default="demanda", max_length=30, verbose_name="Entidade de origem"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="entidade_id",
            field=models.CharField(default="", max_length=64, verbose_name="ID da entidade de origem"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="activity",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="riscos_de_glosa", to="sgp.activity", verbose_name="Atividade",
            ),
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="resolvido_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Resolvido em"),
        ),
        migrations.AddField(
            model_name="glosarisk",
            name="resolvido_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="glosas_risco_resolvidas", to=settings.AUTH_USER_MODEL, verbose_name="Resolvido por",
            ),
        ),
        migrations.AddConstraint(
            model_name="glosarisk",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tipo_situacao", "pago_acima_autorizado")),
                fields=("demand_request_id", "arlo_import_id"),
                name="uniq_glosarisk_solicitacao_import",
            ),
        ),
        migrations.AddConstraint(
            model_name="glosarisk",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tipo_situacao", "demanda_sem_evidencia")),
                fields=("entidade", "entidade_id"),
                name="uniq_glosarisk_sem_evidencia_por_entidade",
            ),
        ),
        migrations.RunPython(preencher_origem_e_atividade, migrations.RunPython.noop),
    ]
