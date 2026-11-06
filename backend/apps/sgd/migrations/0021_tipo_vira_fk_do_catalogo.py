import django.db.models.deletion
from django.db import migrations, models


def recriar_mapeamentos(apps, schema_editor):
    Tipo = apps.get_model("sgd", "TipoSolicitacao")
    Mapeamento = apps.get_model("sgd", "DemandTypeRubricaMapping")
    for tipo in Tipo.objects.all():
        Mapeamento.objects.create(tipo=tipo.slug, rubrica_id=tipo.rubrica_id, ativo=tipo.ativo)


def remover_mapeamento_antigo_da_configuracao(apps, schema_editor):
    apps.get_model("core", "SystemConfig").objects.filter(chave="sgd_mapeamento_tipo_rubrica").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_power_bi_token"),
        ("sgd", "0020_tipo_solicitacao"),
    ]

    operations = [
        migrations.RunPython(remover_mapeamento_antigo_da_configuracao, migrations.RunPython.noop),
        # Na volta, roda depois de a tabela do mapeamento ser recriada.
        migrations.RunPython(migrations.RunPython.noop, recriar_mapeamentos),
        migrations.RemoveConstraint(model_name="demandtyperubricamapping", name="uniq_tipo_rubrica_ativo"),
        migrations.AlterField(
            model_name="demandrequest",
            name="tipo",
            field=models.ForeignKey(
                db_column="tipo", on_delete=django.db.models.deletion.PROTECT, related_name="solicitacoes",
                to="sgd.tiposolicitacao", to_field="slug", verbose_name="Tipo",
            ),
        ),
        migrations.DeleteModel(name="DemandTypeRubricaMapping"),
    ]
