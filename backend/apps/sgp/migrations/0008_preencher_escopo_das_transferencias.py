"""Até aqui só a decisão de recurso extra criava BudgetTransfer: as existentes são
elevação de limite e herdam a demanda do pedido."""
from django.db import migrations
from django.db.models import OuterRef, Subquery


def preencher(apps, schema_editor):
    BudgetTransfer = apps.get_model("sgp", "BudgetTransfer")
    BudgetIncreaseRequest = apps.get_model("sgp", "BudgetIncreaseRequest")
    BudgetTransfer.objects.filter(increase_request__isnull=False).update(
        escopo="elevacao_limite",
        demanda_id=Subquery(
            BudgetIncreaseRequest.objects.filter(pk=OuterRef("increase_request_id")).values("demanda_id")[:1]
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0007_budgettransfer_escopo_e_referencias"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
