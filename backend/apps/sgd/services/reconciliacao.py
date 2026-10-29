"""Conferência do saldo individual do SGD para `manage.py verificar_saldos`."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.sgd.models import Demand, DemandIndividualLimit, DemandRequest
from apps.sgd.models.demand_request import RESERVA_ATIVA

ZERO = Decimal("0")


@contextmanager
def _leitura_total_do_sgd():
    """O comando não passa pelo middleware que define o papel da sessão, e o RLS
    de `sgd_demand` esconderia do usuário de runtime as solicitações cruzadas com
    a demanda: reservas válidas somariam zero e uma reserva sem limite sumiria.
    O papel anterior volta no fim porque `set_config(..., true)` vale até o fim
    da transação externa, não só do savepoint."""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.user_role', true)")
        anterior = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.user_role', 'super-admin', true)")
        yield
        cursor.execute("SELECT set_config('app.user_role', %s, true)", [anterior])


def divergencias_dos_limites() -> list[str]:
    """`valor_comprometido` de cada limite contra a soma das reservas ativas do mesmo
    solicitante e rubrica, sem o excedente (que fica fora do limite), e reservas
    ativas sem limite nenhum."""
    with _leitura_total_do_sgd():
        return _divergencias_dos_limites()


def _divergencias_dos_limites() -> list[str]:
    reservado = (
        DemandRequest.objects.filter(
            RESERVA_ATIVA, demanda__solicitante=OuterRef("solicitante"), rubrica=OuterRef("rubrica"),
        )
        .order_by()
        .values("rubrica")
        .annotate(total=Sum(F("valor_reservado") - F("valor_excedente")))
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


_MOEDA = DecimalField(max_digits=14, decimal_places=2)


def divergencias_dos_totais() -> list[str]:
    """Totais materializados de cada demanda contra a soma das solicitações dela."""
    with _leitura_total_do_sgd():
        return _divergencias_dos_totais()


def _divergencias_dos_totais() -> list[str]:
    somas = {
        campo: Coalesce(Sum(f"solicitacoes__{campo}"), Value(ZERO, output_field=_MOEDA))
        for campo in ("valor_estimado", "valor_autorizado", "valor_pago")
    }
    demandas = Demand.objects.order_by("pk").annotate(**{f"soma_{campo}": soma for campo, soma in somas.items()})
    divergentes = demandas.filter(
        ~Q(valor_estimado_total=F("soma_valor_estimado"))
        | ~Q(valor_autorizado_total=F("soma_valor_autorizado"))
        | ~Q(valor_pago_total=F("soma_valor_pago"))
    )
    return [
        f"Demanda #{demanda.pk}: totais estimado/autorizado/pago = {demanda.valor_estimado_total}/"
        f"{demanda.valor_autorizado_total}/{demanda.valor_pago_total} mas as solicitações somam "
        f"{demanda.soma_valor_estimado}/{demanda.soma_valor_autorizado}/{demanda.soma_valor_pago}"
        for demanda in divergentes
    ]
