from django.db import migrations


def sanea_titularidade(apps, schema_editor):
    UPF = apps.get_model("sgp", "UPF")
    MembroFamilia = apps.get_model("sgp", "MembroFamilia")

    for membro in MembroFamilia.objects.filter(parentesco="titular").select_related("upf"):
        if membro.upf_id and membro.upf.titular_id != membro.pk:
            membro.parentesco = "filho"
            membro.save(update_fields=["parentesco"])

    for upf in UPF.objects.select_related("titular"):
        if upf.titular_id and upf.titular.parentesco != "titular":
            MembroFamilia.objects.filter(pk=upf.titular_id).update(parentesco="titular")


def sanea_cpf_duplicado(apps, schema_editor):
    from django.db.models import Count

    MembroFamilia = apps.get_model("sgp", "MembroFamilia")

    duplicados = (
        MembroFamilia.objects.filter(cpf__gt="")
        .values("cpf")
        .annotate(cnt=Count("pk"))
        .filter(cnt__gt=1)
    )

    for item in duplicados:
        membros = MembroFamilia.objects.filter(cpf=item["cpf"]).order_by("criado_em")
        primeiros = membros[1:]
        MembroFamilia.objects.filter(pk__in=[m.pk for m in primeiros]).update(cpf="")


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0009_atualiza_choices_genero_cor_raca_escolaridade_saude_seguridade"),
    ]

    operations = [
        migrations.RunPython(sanea_titularidade, migrations.RunPython.noop),
        migrations.RunPython(sanea_cpf_duplicado, migrations.RunPython.noop),
    ]
