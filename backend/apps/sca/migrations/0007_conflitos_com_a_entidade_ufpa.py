from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Replace


def _conflitos(apps, de, para):
    """`campo` volta ao objeto na resolução do conflito, então precisa do nome novo do campo."""
    conflitos = apps.get_model("sca", "ConflictLog").objects
    conflitos.filter(entidade=de).update(entidade=para)
    conflitos.filter(campo__contains=de).update(campo=Replace("campo", Value(de), Value(para)))


def nomes_novos(apps, schema_editor):
    _conflitos(apps, "upf", "ufpa")


def nomes_antigos(apps, schema_editor):
    _conflitos(apps, "ufpa", "upf")


class Migration(migrations.Migration):

    dependencies = [
        ("sca", "0006_syncdevice_espelho_saldo"),
    ]

    operations = [
        migrations.RunPython(nomes_novos, nomes_antigos),
    ]
