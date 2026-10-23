"""Conferência do saldo individual do SGD para `manage.py verificar_saldos`."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Exists, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.sgd.models import DemandIndividualLimit, DemandRequest
from apps.sgd.models.demand_request import RESERVA_ATIVA

ZERO = Decimal("0")


def divergencias_dos_limites() -> list[str]:
    """`valor_comprometido` de cada limite contra a soma do `valor_reservado` das
    solicitações com reserva ativa do mesmo solicitante e rubrica, e reservas
    ativas sem limite nenhum."""
    reservado = (
        DemandRequest.objects.filter(
            RESERVA_ATIVA, demanda__solicitante=OuterRef("solicitante"), rubrica=OuterRef("rubrica"),
        )
        .order_by()
        .values("rubrica")
        .annotate(total=Sum("valor_reservado"))
        .values("total")
    )
    limites = DemandIndividualLimit.objects.annotate(
        reservado=Coalesce(
            Subquery(reservado, output_field=DecimalField(max_digits=14, decimal_places=2)),
            Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
        ),
    ).order_by("pk")

    divergencias = [
        f"Limite individual #{limite.pk}: valor_comprometido={limite.valor_comprometido} "
        f"mas as reservas ativas somam {limite.reservado}"
        for limite in limites
        if limite.valor_comprometido != limite.reservado
    ]

    tem_limite = DemandIndividualLimit.objects.filter(
        solicitante=OuterRef("demanda__solicitante"), rubrica=OuterRef("rubrica"),
    )
    sem_limite = DemandRequest.objects.filter(RESERVA_ATIVA).exclude(Exists(tem_limite))
    divergencias += [
        f"Solicitação #{pk}: reserva ativa de {valor} sem limite individual do solicitante na rubrica"
        for pk, valor in sem_limite.order_by("pk").values_list("pk", "valor_reservado")
    ]
    return divergencias
