"""Renomeia, sem copiar dados. O autodetector veria apagar `UPF` e criar `UFPA`, por isso é escrita à mão."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _exportacoes(apps, de, para):
    apps.get_model("sgp", "ExportJob").objects.filter(tipo=de).update(tipo=para)


def tipo_novo_das_exportacoes(apps, schema_editor):
    _exportacoes(apps, "upfs", "ufpas")


def tipo_antigo_das_exportacoes(apps, schema_editor):
    _exportacoes(apps, "ufpas", "upfs")


# O RenameModel renomeia o ContentType, mas não as permissões: sem isto, as
# antigas ficariam órfãs e o post_migrate criaria outras, sem os grupos e
# usuários que já tinham as antigas.
NOMES_DAS_PERMISSOES = {
    # codename do modelo: (codename novo, verbose_name novo)
    "upf": ("ufpa", "UFPA"),
    "upfdocument": ("ufpadocument", "Documento da UFPA"),
}
NOMES_ANTIGOS_DAS_PERMISSOES = {
    "ufpa": ("upf", "UPF"),
    "ufpadocument": ("upfdocument", "Documento da UPF"),
}
ACOES = ("add", "change", "delete", "view")


def _permissoes(apps, nomes):
    Permission = apps.get_model("auth", "Permission")
    for de, (para, verbose_name) in nomes.items():
        for acao in ACOES:
            antiga = Permission.objects.filter(content_type__app_label="sgp", codename=f"{acao}_{de}").first()
            if antiga is None:
                continue
            if Permission.objects.filter(content_type=antiga.content_type, codename=f"{acao}_{para}").exists():
                continue
            antiga.codename = f"{acao}_{para}"
            antiga.name = f"Can {acao} {verbose_name}"
            antiga.save(update_fields=["codename", "name"])


def permissoes_novas(apps, schema_editor):
    _permissoes(apps, NOMES_DAS_PERMISSOES)


def permissoes_antigas(apps, schema_editor):
    _permissoes(apps, NOMES_ANTIGOS_DAS_PERMISSOES)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sgp", "0020_valores_monetarios_em_14_digitos"),
    ]

    operations = [
        # Os índices e a constraint citam o campo pelo nome, então saem antes e voltam com o nome novo.
        migrations.RemoveIndex(model_name="upf", name="idx_upf_municipio"),
        migrations.RemoveIndex(model_name="upf", name="idx_upf_territorio"),
        migrations.RemoveIndex(model_name="upf", name="idx_upf_projeto"),
        migrations.RemoveIndex(model_name="upf", name="idx_upf_comunidade"),
        migrations.RemoveIndex(model_name="upfdocument", name="idx_upfdoc_upf_criado"),
        migrations.RemoveIndex(model_name="upfdocument", name="idx_upfdoc_arquivo_key"),
        migrations.RemoveIndex(model_name="membrofamilia", name="idx_membro_upf"),
        migrations.RemoveIndex(model_name="production", name="idx_production_upf"),
        migrations.RemoveIndex(model_name="formresponse", name="idx_form_response_upf_data"),
        migrations.RemoveConstraint(model_name="membrofamilia", name="unique_titular_por_upf"),
        migrations.RenameModel(old_name="UPF", new_name="UFPA"),
        migrations.RenameModel(old_name="UPFDocument", new_name="UFPADocument"),
        migrations.RenameField(model_name="formresponse", old_name="upf", new_name="ufpa"),
        migrations.RenameField(model_name="membrofamilia", old_name="upf", new_name="ufpa"),
        migrations.RenameField(model_name="production", old_name="upf", new_name="ufpa"),
        migrations.RenameField(model_name="ufpadocument", old_name="upf", new_name="ufpa"),
        migrations.RenameField(model_name="activity", old_name="upfs_participantes", new_name="ufpas_participantes"),
        migrations.AlterModelOptions(
            name="ufpa",
            options={
                "base_manager_name": "all_objects", "ordering": ["-criado_em"],
                "verbose_name": "UFPA", "verbose_name_plural": "UFPAs",
            },
        ),
        migrations.AlterModelOptions(
            name="ufpadocument",
            options={
                "ordering": ["-criado_em"],
                "verbose_name": "Documento da UFPA", "verbose_name_plural": "Documentos da UFPA",
            },
        ),
        migrations.AlterField(
            model_name="activity",
            name="ufpas_participantes",
            field=models.ManyToManyField(
                blank=True, db_table="sgp_activityufpa", related_name="atividades", to="sgp.ufpa",
                verbose_name="UFPAs Participantes",
            ),
        ),
        migrations.AlterField(
            model_name="exportjob",
            name="tipo",
            field=models.CharField(
                choices=[("plano_trabalho", "Plano de Trabalho"), ("atividades", "Atividades"), ("ufpas", "UFPAs")],
                max_length=20, verbose_name="Tipo",
            ),
        ),
        migrations.AlterField(
            model_name="formresponse",
            name="ufpa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="form_responses", to="sgp.ufpa",
                verbose_name="UFPA",
            ),
        ),
        migrations.AlterField(
            model_name="membrofamilia",
            name="ufpa",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="membros",
                to="sgp.ufpa", verbose_name="UFPA",
            ),
        ),
        migrations.AlterField(
            model_name="production",
            name="ufpa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="producoes", to="sgp.ufpa",
                verbose_name="UFPA",
            ),
        ),
        migrations.AlterField(
            model_name="ufpa",
            name="comunidade",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ufpas",
                to="sgp.comunidade", verbose_name="Comunidade",
            ),
        ),
        migrations.AlterField(
            model_name="ufpa",
            name="municipio",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="ufpas", to="core.municipality",
                verbose_name="Município",
            ),
        ),
        migrations.AlterField(
            model_name="ufpa",
            name="projeto",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="ufpas", to="sgp.projeto",
                verbose_name="Projeto",
            ),
        ),
        migrations.AlterField(
            model_name="ufpa",
            name="territorio",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="ufpas", to="core.territory",
                verbose_name="Território",
            ),
        ),
        migrations.AlterField(
            model_name="ufpa",
            name="titular",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT, related_name="ufpa_titular", to="sgp.membrofamilia",
                verbose_name="Titular",
            ),
        ),
        migrations.AlterField(
            model_name="ufpadocument",
            name="criado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentos_ufpa_criados", to=settings.AUTH_USER_MODEL, verbose_name="Criado por",
            ),
        ),
        migrations.AlterField(
            model_name="ufpadocument",
            name="ufpa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="documentos", to="sgp.ufpa",
                verbose_name="UFPA",
            ),
        ),
        migrations.AddIndex(
            model_name="ufpa",
            index=models.Index(fields=["municipio"], name="idx_ufpa_municipio"),
        ),
        migrations.AddIndex(
            model_name="ufpa",
            index=models.Index(fields=["territorio"], name="idx_ufpa_territorio"),
        ),
        migrations.AddIndex(
            model_name="ufpa",
            index=models.Index(fields=["projeto"], name="idx_ufpa_projeto"),
        ),
        migrations.AddIndex(
            model_name="ufpa",
            index=models.Index(fields=["comunidade"], name="idx_ufpa_comunidade"),
        ),
        migrations.AddIndex(
            model_name="ufpadocument",
            index=models.Index(fields=["ufpa", "-criado_em"], name="idx_ufpadoc_ufpa_criado"),
        ),
        migrations.AddIndex(
            model_name="ufpadocument",
            index=models.Index(fields=["arquivo_key"], name="idx_ufpadoc_arquivo_key"),
        ),
        migrations.AddIndex(
            model_name="membrofamilia",
            index=models.Index(fields=["ufpa"], name="idx_membro_ufpa"),
        ),
        migrations.AddIndex(
            model_name="production",
            index=models.Index(fields=["ufpa"], name="idx_production_ufpa"),
        ),
        migrations.AddIndex(
            model_name="formresponse",
            index=models.Index(fields=["ufpa", "-data_preenchimento"], name="idx_form_response_ufpa_data"),
        ),
        migrations.AddConstraint(
            model_name="membrofamilia",
            constraint=models.UniqueConstraint(
                condition=models.Q(("grau_parentesco", "titular")),
                fields=("ufpa",),
                name="unique_titular_por_ufpa",
            ),
        ),
        migrations.RunPython(tipo_novo_das_exportacoes, tipo_antigo_das_exportacoes),
        migrations.RunPython(permissoes_novas, permissoes_antigas),
    ]
