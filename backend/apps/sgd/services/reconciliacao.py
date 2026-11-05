"""Conferência do saldo individual do SGD para `manage.py verificar_saldos`."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import DecimalField, Exists, F, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.sgd.models import Demand, DemandRequest
from apps.sgd.models.demand_request import RESERVA_ATIVA
from apps.sgp.models import SpendingLimit

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
    reservado = {
        (linha["demanda__solicitante_id"], linha["rubrica_id"]): linha["total"]
        for linha in DemandRequest.objects.filter(RESERVA_ATIVA)
        .order_by()
        .values("demanda__solicitante_id", "rubrica_id")
        .annotate(total=Sum(F("valor_reservado") - F("valor_excedente")))
    }
    # Por solicitante e rubrica, somando os períodos: uma reserva fica na linha em que foi feita.
    limites = (
        SpendingLimit.objects.filter(escopo=SpendingLimit.Escopo.INDIVIDUAL)
        .order_by("user_id", "rubrica_id")
        .values("user_id", "rubrica_id")
        .annotate(comprometido=Sum("valor_comprometido"))
    )
    divergencias = [
        f"Limite individual do usuário #{limite['user_id']} na rubrica #{limite['rubrica_id']}: "
        f"valor_comprometido={limite['comprometido']} mas as reservas ativas somam "
        f"{reservado.get((limite['user_id'], limite['rubrica_id']), ZERO)}"
        for limite in limites
        if limite["comprometido"] != reservado.get((limite["user_id"], limite["rubrica_id"]), ZERO)
    ]

    tem_limite = SpendingLimit.objects.filter(
        escopo=SpendingLimit.Escopo.INDIVIDUAL,
        user=OuterRef("demanda__solicitante"), rubrica=OuterRef("rubrica"),
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
