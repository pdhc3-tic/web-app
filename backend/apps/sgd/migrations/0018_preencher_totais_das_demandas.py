"""Preenche os totais materializados de cada demanda com a soma das solicitações.
Recalcula tudo a cada execução, então rodar de novo dá o mesmo resultado."""
from decimal import Decimal

from django.db import migrations
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

MOEDA = DecimalField(max_digits=14, decimal_places=2)


def _soma(DemandRequest, campo):
    total = (
        DemandRequest.objects.filter(demanda=OuterRef("pk"))
        .order_by()
        .values("demanda")
        .annotate(total=Sum(campo))
        .values("total")[:1]
    )
    return Coalesce(Subquery(total, output_field=MOEDA), Value(Decimal("0"), output_field=MOEDA))


def preencher(apps, schema_editor):
    Demand = apps.get_model("sgd", "Demand")
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    Demand.objects.update(
        valor_estimado_total=_soma(DemandRequest, "valor_estimado"),
        valor_autorizado_total=_soma(DemandRequest, "valor_autorizado"),
        valor_pago_total=_soma(DemandRequest, "valor_pago"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0017_demand_totais_materializados"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
