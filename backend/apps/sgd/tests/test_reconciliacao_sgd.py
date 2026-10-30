"""`manage.py verificar_saldos` confere também o limite individual e os totais das demandas do SGD."""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.sgd.models import Demand, DemandIndividualLimit, DemandRequest
from apps.sgd.services import balance as balance_service
from apps.sgd.services.reconciliacao import divergencias_dos_limites, divergencias_dos_totais

pytestmark = pytest.mark.django_db

# A suíte conecta como superusuário, que ignora o RLS: o teste troca para um
# papel sem BYPASSRLS, com os mesmos GRANTs de leitura do usuário de runtime.
# Criado dentro da transação do teste, some no rollback.
_PAPEL_DE_RUNTIME = "sgd_reconciliacao_runtime"


@contextmanager
def _como_comando_com_credenciais_de_runtime():
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {_PAPEL_DE_RUNTIME} NOLOGIN NOBYPASSRLS;")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"SET LOCAL ROLE {_PAPEL_DE_RUNTIME};")
        cursor.execute("SELECT set_config('app.user_role', '', true)")
        cursor.execute("SELECT set_config('app.current_user_id', '', true)")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE;")


def test_passa_com_o_saldo_movido_pelos_servicos(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=Decimal("800"), usuario=solicitante_rn,
    )

    assert divergencias_dos_limites() == []
    call_command("verificar_saldos")


def test_falha_com_comprometido_diferente_das_reservas_ativas(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("999"))

    assert divergencias_dos_limites() == [
        f"Limite individual #{limite_individual_rn.pk}: valor_comprometido=999.00 "
        "mas as reservas ativas somam 1000.00"
    ]
    with pytest.raises(CommandError, match=f"Limite individual #{limite_individual_rn.pk}"):
        call_command("verificar_saldos")


def test_reserva_executada_nao_conta_no_comprometido(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.executar_duas_travas(
        demand_request=demand_request_rn, valor_pago=Decimal("900"), usuario=solicitante_rn,
    )

    assert divergencias_dos_limites() == []


def test_falha_com_reserva_ativa_sem_limite(demand_request_rn):
    DemandRequest.objects.filter(pk=demand_request_rn.pk).update(valor_reservado=Decimal("1000"))

    assert divergencias_dos_limites() == [
        f"Solicitação #{demand_request_rn.pk}: reserva ativa de 1000.00 sem limite individual "
        "do solicitante na rubrica"
    ]


def test_reserva_valida_nao_diverge_com_o_papel_de_runtime(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    with _como_comando_com_credenciais_de_runtime():
        divergencias = divergencias_dos_limites()
        call_command("verificar_saldos")

    assert divergencias == []


def test_reserva_sem_limite_aparece_com_o_papel_de_runtime(demand_request_rn):
    DemandRequest.objects.filter(pk=demand_request_rn.pk).update(valor_reservado=Decimal("1000"))

    with _como_comando_com_credenciais_de_runtime():
        divergencias = divergencias_dos_limites()

    assert divergencias == [
        f"Solicitação #{demand_request_rn.pk}: reserva ativa de 1000.00 sem limite individual "
        "do solicitante na rubrica"
    ]


def test_conferencia_devolve_o_papel_da_sessao():
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.user_role', 'adt-acr', true)")
        divergencias_dos_limites()
        cursor.execute("SELECT current_setting('app.user_role', true)")
        assert cursor.fetchone()[0] == "adt-acr"


def test_reserva_com_excedente_nao_diverge(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=Decimal("5300"), usuario=solicitante_rn,
        excedente=Decimal("300"),
    )

    assert divergencias_dos_limites() == []


def test_falha_com_total_da_demanda_diferente_das_solicitacoes(demand_request_rn):
    Demand.objects.filter(pk=demand_request_rn.demanda_id).update(valor_estimado_total=Decimal("1"))

    divergencias = divergencias_dos_totais()

    assert len(divergencias) == 1
    assert divergencias[0].startswith(f"Demanda #{demand_request_rn.demanda_id}: totais estimado/autorizado/pago")
    with pytest.raises(CommandError, match=f"Demanda #{demand_request_rn.demanda_id}"):
        call_command("verificar_saldos")


def test_total_divergente_aparece_com_o_papel_de_runtime(demand_request_rn):
    Demand.objects.filter(pk=demand_request_rn.demanda_id).update(valor_estimado_total=Decimal("1"))

    with _como_comando_com_credenciais_de_runtime():
        divergencias = divergencias_dos_totais()

    assert len(divergencias) == 1
