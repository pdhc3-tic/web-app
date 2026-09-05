"""
Issue #228 — casa `Activity.parceiros_livres` (texto livre) com
`core.Organization` por nome normalizado, preservando em
`parceiros_livres` tudo o que não corresponder a nenhuma organização
cadastrada. Nenhum parceiro é descartado: cada nome termina vinculado a
uma Organization (via M2M) ou mantido como texto livre.
"""
import logging

from django.db import migrations

from apps.sgp.parceiros_matching import casar_parceiros, dividir_parceiros_texto

logger = logging.getLogger(__name__)


def migrar_parceiros_para_organizacoes(apps, schema_editor):
    Activity = apps.get_model("sgp", "Activity")
    Organization = apps.get_model("core", "Organization")

    organizacoes = list(Organization.objects.values_list("id", "nome"))

    atividades_processadas = 0
    total_casados = 0
    total_nao_casados = 0

    for activity in Activity.objects.exclude(parceiros_livres="").iterator():
        nomes = dividir_parceiros_texto(activity.parceiros_livres)
        if not nomes:
            continue

        ids_casados, nomes_nao_casados = casar_parceiros(nomes, organizacoes)

        if ids_casados:
            activity.parceiros_organizacoes.set(ids_casados)

        novo_texto = "; ".join(nomes_nao_casados)
        if novo_texto != activity.parceiros_livres:
            activity.parceiros_livres = novo_texto
            activity.save(update_fields=["parceiros_livres"])

        atividades_processadas += 1
        total_casados += len(ids_casados)
        total_nao_casados += len(nomes_nao_casados)

    logger.info(
        "[Issue #228] migracao parceiros->organizacoes: "
        "%d atividades processadas, %d parceiros casados com Organization, "
        "%d permaneceram em parceiros_livres.",
        atividades_processadas, total_casados, total_nao_casados,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0024_activity_parceiros_organizacoes"),
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.RunPython(migrar_parceiros_para_organizacoes, migrations.RunPython.noop),
    ]
