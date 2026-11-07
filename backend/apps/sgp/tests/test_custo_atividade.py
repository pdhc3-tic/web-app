"""Custo previsto e realizado na ficha da atividade."""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from django.db import connection

from apps.sgd.models import Demand
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.services.activity import custos_da_atividade
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/sgp/atividades/"
_PAPEL_DE_RUNTIME = "sgp_custo_atividade_runtime"


def _demanda(activity, status, estimado, *, autorizado=None, pago=None):
    demanda = DemandFactory(activity=activity, status=status)
    DemandRequestFactory(demanda=demanda, valor_estimado=estimado, valor_autorizado=autorizado, valor_pago=pago)
    return demanda


@contextmanager
def _sessao_de_adt(usuario_id):
    """O usuário dos testes ignora o RLS: aqui a consulta passa pela política, como em produção."""
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {_PAPEL_DE_RUNTIME} NOLOGIN NOBYPASSRLS;")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"SET LOCAL ROLE {_PAPEL_DE_RUNTIME};")
        cursor.execute("SELECT set_config('app.user_role', 'adt-acr', true)")
        cursor.execute("SELECT set_config('app.current_user_id', %s, true)", [str(usuario_id)])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE;")


@pytest.mark.parametrize("status,entra", [
    ("rascunho", True),
    ("submetida", True),
    ("devolvida", True),
    ("pre_autorizada", True),
    ("autorizada", True),
    ("em_atendimento", True),
    ("concluida", False),
    ("cancelada", False),
    ("recusada", False),
])
def test_previsto_soma_o_estimado_das_demandas_ainda_nao_concluidas(status, entra):
    atividade = ActivityFactory()
    _demanda(atividade, status, 500)

    assert custos_da_atividade(atividade)["previsto"] == (Decimal("500.00") if entra else None)


@pytest.mark.parametrize("status", ["em_atendimento", "cancelada"])
def test_realizado_so_conta_demanda_concluida(status):
    atividade = ActivityFactory()
    _demanda(atividade, status, 500, autorizado=500, pago=500)

    assert custos_da_atividade(atividade)["realizado"] is None


@pytest.mark.parametrize("autorizado,pago,realizado", [
    (Decimal("1000"), Decimal("800"), Decimal("800.00")),
    (Decimal("1000"), Decimal("1200"), Decimal("1000.00")),
    (None, Decimal("700"), Decimal("500.00")),
])
def test_realizado_e_o_executado_e_nao_passa_do_autorizado(autorizado, pago, realizado):
    atividade = ActivityFactory()
    _demanda(atividade, "concluida", 500, autorizado=autorizado, pago=pago)

    assert custos_da_atividade(atividade)["realizado"] == realizado


def test_soma_as_solicitacoes_e_ignora_outra_atividade():
    atividade = ActivityFactory()
    aberta = _demanda(atividade, "submetida", 300)
    DemandRequestFactory(demanda=aberta, valor_estimado=200)
    _demanda(atividade, "concluida", 400, autorizado=400, pago=400)
    _demanda(ActivityFactory(), "submetida", 9000)
    _demanda(ActivityFactory(), "concluida", 9000, autorizado=9000, pago=9000)

    assert custos_da_atividade(atividade) == {"previsto": Decimal("500.00"), "realizado": Decimal("400.00")}


def test_total_nao_depende_de_quem_le_apesar_do_rls():
    atividade = ActivityFactory()
    propria = _demanda(atividade, "submetida", 300)
    _demanda(atividade, "submetida", 200)
    _demanda(atividade, "concluida", 400, autorizado=400, pago=400)

    with _sessao_de_adt(propria.solicitante_id):
        assert Demand.objects.filter(activity=atividade).count() == 1
        custos = custos_da_atividade(atividade)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.user_role', true)")
            assert cursor.fetchone()[0] == "adt-acr"

    assert custos == {"previsto": Decimal("500.00"), "realizado": Decimal("400.00")}


class TestNaFicha:
    def test_detalhe_traz_os_dois_custos_com_duas_casas(self, auth_client):
        atividade = ActivityFactory()
        _demanda(atividade, "submetida", 300)
        _demanda(atividade, "concluida", 400, autorizado=400, pago=1000)

        dados = auth_client.get(f"{LIST_URL}{atividade.pk}/").data

        assert (dados["custo_previsto"], dados["custo_realizado"]) == ("300.00", "400.00")

    def test_sem_demandas_o_custo_e_zero(self, auth_client):
        dados = auth_client.get(f"{LIST_URL}{ActivityFactory().pk}/").data

        assert (dados["custo_previsto"], dados["custo_realizado"]) == ("0.00", "0.00")

    def test_custo_nao_e_gravavel(self, auth_client_super_admin):
        atividade = ActivityFactory()

        resposta = auth_client_super_admin.patch(
            f"{LIST_URL}{atividade.pk}/", {"custo_previsto": "999.00"}, format="json",
        )

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["custo_previsto"] == "0.00"

    def test_lista_nao_traz_custo(self, auth_client):
        ActivityFactory()

        assert "custo_previsto" not in auth_client.get(LIST_URL).data["results"][0]
