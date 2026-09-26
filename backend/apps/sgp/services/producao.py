"""Indicadores da produção consolidada das UPFs."""

from decimal import Decimal

from django.db.models import Count, Sum

PRINCIPAIS_CULTURAS_LIMITE = 5


def indicadores_producao(queryset) -> dict:
    """Totais sobre um queryset de `Production` já filtrado e no escopo do usuário."""
    queryset = queryset.order_by()
    totais = queryset.aggregate(
        total_upfs_produtoras=Count("upf", distinct=True),
        area_total_ha=Sum("area_ha"),
    )
    principais_culturas = (
        queryset.filter(cultura__isnull=False)
        .values("cultura__nome")
        .annotate(count=Count("upf", distinct=True))
        .order_by("-count", "cultura__nome")[:PRINCIPAIS_CULTURAS_LIMITE]
    )
    area_total = totais["area_total_ha"] or Decimal("0")
    return {
        "total_upfs_produtoras": totais["total_upfs_produtoras"],
        "area_total_ha": f"{area_total:.2f}",
        "principais_culturas": [
            {"nome": item["cultura__nome"], "count": item["count"]}
            for item in principais_culturas
        ],
    }
