from django.db import migrations


def seed_sca_sync_alerta_dias(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.get_or_create(
        chave="sca_sync_alerta_dias",
        defaults={
            "valor": "7",
            "tipo": "integer",
            "descricao": "Dias sem sincronização para alerta vermelho",
        },
    )


def reverse_seed(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(chave="sca_sync_alerta_dias").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_merge_20260804_1648"),
    ]

    operations = [
        migrations.RunPython(seed_sca_sync_alerta_dias, reverse_seed),
    ]
