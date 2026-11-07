from django.db import migrations


def _conflitos(apps, de, para):
    apps.get_model("sca", "ConflictLog").objects.filter(entidade=de).update(entidade=para)


def entidade_nova(apps, schema_editor):
    _conflitos(apps, "upf", "ufpa")


def entidade_antiga(apps, schema_editor):
    _conflitos(apps, "ufpa", "upf")


class Migration(migrations.Migration):

    dependencies = [
        ("sca", "0006_syncdevice_espelho_saldo"),
    ]

    operations = [
        migrations.RunPython(entidade_nova, entidade_antiga),
    ]
