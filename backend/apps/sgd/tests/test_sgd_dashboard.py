import time
from datetime import datetime, time as dtime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.sgd.models.demand import Demand
from apps.sgd.services import business_days
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.models.budget import BudgetAllocation
from apps.sgp.tests.factories import ActivityFactory, BudgetAllocationFactory, WorkPlanAcaoFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/dashboard/"


def _demanda(activity, solicitante, status, valor=0, *, dias_atras=0, hora=12):
    """Demanda no `status`, com uma solicitação de `valor` e `status_alterado_em`
    recuado `dias_atras` dias corridos (sempre ao meio-dia, para o dia local não
    virar na conversão)."""
    demanda = DemandFactory(activity=activity, solicitante=solicitante, status=status)
    DemandRequestFactory(demanda=demanda, valor_estimado=valor)
    dia = timezone.localdate() - timedelta(days=dias_atras)
    Demand.objects.filter(pk=demanda.pk).update(
        status_alterado_em=timezone.make_aware(datetime.combine(dia, dtime(hora))),
    )
    return demanda


def _atras_em_dias_uteis(dias_uteis, uf="RN"):
    hoje = timezone.localdate()
    referencia = hoje
    while business_days.dias_uteis_entre(referencia, hoje, uf=uf) < dias_uteis:
        referencia -= timedelta(days=1)
    return (hoje - referencia).days


def _ids(bloco):
    return [item["id"] for item in bloco["itens"]]


# --- autenticação -----------------------------------------------------------

def test_dashboard_exige_autenticacao(api_client):
    assert api_client.get(URL).status_code == 401


# --- fila "Aguardando minha ação" -------------------------------------------

def test_fila_ordenada_por_espera_e_em_empate_por_valor(auth_client_ugp, activity_rn, solicitante_rn):
    recente = _demanda(activity_rn, solicitante_rn, "pre_autorizada", valor=9_000, dias_atras=1)
    antiga_barata = _demanda(activity_rn, solicitante_rn, "pre_autorizada", valor=100, dias_atras=3)
    antiga_cara = _demanda(activity_rn, solicitante_rn, "pre_autorizada", valor=800, dias_atras=3)
    # horário diferente no mesmo dia — ainda é empate de espera
    Demand.objects.filter(pk=antiga_cara.pk).update(
        status_alterado_em=timezone.make_aware(
            datetime.combine(timezone.localdate() - timedelta(days=3), dtime(15)),
        ),
    )

    fila = auth_client_ugp.get(URL).json()["fila_aguardando_acao"]

    assert fila["total"] == 3
    assert _ids(fila) == [antiga_cara.pk, antiga_barata.pk, recente.pk]
    assert Decimal(fila["itens"][0]["valor_estimado"]) == Decimal("800.00")
    assert fila["itens"][0]["dias_em_espera"] == 3


def test_fila_so_traz_status_que_o_perfil_decide(auth_client_ugp, activity_rn, solicitante_rn):
    pre = _demanda(activity_rn, solicitante_rn, "pre_autorizada")
    _demanda(activity_rn, solicitante_rn, "submetida")
    _demanda(activity_rn, solicitante_rn, "autorizada")

    fila = auth_client_ugp.get(URL).json()["fila_aguardando_acao"]

    assert _ids(fila) == [pre.pk]


# --- contadores por status ---------------------------------------------------

def _contagem(payload):
    return {linha["status"]: linha["total"] for linha in payload["contagem_por_status"]}


def test_contadores_do_articulador(auth_client_articulador_rn, activity_rn, solicitante_rn):
    _demanda(activity_rn, solicitante_rn, "submetida")
    _demanda(activity_rn, solicitante_rn, "submetida")
    _demanda(activity_rn, solicitante_rn, "rascunho")  # fora do escopo do Articulador

    contagem = _contagem(auth_client_articulador_rn.get(URL).json())

    assert set(contagem) == {"submetida", "devolvida", "pre_autorizada"}
    assert contagem["submetida"] == 2
    assert contagem["devolvida"] == 0


def test_contadores_da_ugp(auth_client_ugp, activity_rn, solicitante_rn):
    _demanda(activity_rn, solicitante_rn, "pre_autorizada")
    _demanda(activity_rn, solicitante_rn, "autorizada")
    _demanda(activity_rn, solicitante_rn, "autorizada")
    _demanda(activity_rn, solicitante_rn, "recusada")
    _demanda(activity_rn, solicitante_rn, "submetida")  # não é relevante p/ UGP

    contagem = _contagem(auth_client_ugp.get(URL).json())

    assert contagem == {"pre_autorizada": 1, "autorizada": 2, "recusada": 1}


def test_contadores_da_fgd(auth_client_fgd, activity_rn, solicitante_rn):
    _demanda(activity_rn, solicitante_rn, "autorizada")
    _demanda(activity_rn, solicitante_rn, "em_atendimento")
    _demanda(activity_rn, solicitante_rn, "concluida")
    _demanda(activity_rn, solicitante_rn, "concluida")
    _demanda(activity_rn, solicitante_rn, "recusada")

    contagem = _contagem(auth_client_fgd.get(URL).json())

    assert contagem == {"autorizada": 1, "em_atendimento": 1, "concluida": 2}


# --- escopo por território ---------------------------------------------------

def test_articulador_nao_ve_demandas_de_outro_estado(
    auth_client_articulador_rn, activity_rn, solicitante_rn, municipio_ce,
):
    do_rn = _demanda(activity_rn, solicitante_rn, "submetida")
    activity_ce = ActivityFactory(municipio=municipio_ce, acao=WorkPlanAcaoFactory())
    do_ce = _demanda(activity_ce, solicitante_rn, "submetida")

    payload = auth_client_articulador_rn.get(URL).json()

    assert _ids(payload["fila_aguardando_acao"]) == [do_rn.pk]
    assert do_ce.pk not in _ids(payload["fila_aguardando_acao"])
    assert _contagem(payload)["submetida"] == 1


def test_adt_so_ve_as_proprias_demandas(auth_client_solicitante, activity_rn, solicitante_rn):
    from apps.core.tests.factories import UserFactory

    propria = _demanda(activity_rn, solicitante_rn, "devolvida")
    _demanda(activity_rn, UserFactory(), "devolvida")

    payload = auth_client_solicitante.get(URL).json()

    assert payload["fila_aguardando_acao"]["total"] == 0
    assert _contagem(payload)["devolvida"] == 1
    assert propria.pk not in _ids(payload["fila_aguardando_acao"])


# --- alertas de saldo --------------------------------------------------------

def _alocacao_nacional(activity, rubrica, *, alocado, comprometido):
    return BudgetAllocationFactory(
        meta=activity.acao.meta, rubrica=rubrica, nivel=BudgetAllocation.Nivel.NACIONAL,
        territorio=None, estado=None, valor_alocado=alocado, valor_comprometido=comprometido,
    )


def test_alertas_refletem_faixa_amarela_e_vermelha_e_omitem_verde(
    auth_client_ugp, activity_rn, rubrica_diarias,
):
    from apps.sgp.tests.factories import BudgetRubricaFactory, WorkPlanMetaFactory

    _alocacao_nacional(activity_rn, rubrica_diarias, alocado=1_000, comprometido=950)  # vermelho (≥ 90%)
    amarela = BudgetRubricaFactory(slug="passagens", nome="Passagens")
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=amarela, nivel=BudgetAllocation.Nivel.NACIONAL,
        territorio=None, estado=None, valor_alocado=1_000, valor_comprometido=750,  # amarelo (≥ 70%)
    )
    verde = BudgetRubricaFactory(slug="material", nome="Material")
    BudgetAllocationFactory(
        meta=WorkPlanMetaFactory(), rubrica=verde, nivel=BudgetAllocation.Nivel.NACIONAL,
        territorio=None, estado=None, valor_alocado=1_000, valor_comprometido=100,
    )

    alertas = auth_client_ugp.get(URL).json()["alertas_saldo"]

    assert [(a["rubrica_slug"], a["faixa"]) for a in alertas] == [("diarias", "vermelho"), ("passagens", "amarelo")]
    assert all(a["nivel"] == "nacional" for a in alertas)
    assert all(a["estado_sigla"] is None and a["territorio_id"] is None for a in alertas)


def test_alertas_do_articulador_ficam_no_escopo_do_estado(
    auth_client_articulador_rn, activity_rn, rubrica_diarias, municipio_rn, municipio_ce,
):
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        estado=municipio_rn.state, territorio=None, valor_alocado=1_000, valor_comprometido=950,
    )
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        estado=municipio_ce.state, territorio=None, valor_alocado=1_000, valor_comprometido=950,
    )

    alertas = auth_client_articulador_rn.get(URL).json()["alertas_saldo"]

    assert len(alertas) == 1
    assert alertas[0]["nivel"] == "estadual"
    assert alertas[0]["faixa"] == "vermelho"
    assert alertas[0]["estado_sigla"] == "RN"
    assert alertas[0]["territorio_id"] is None


def test_alertas_do_articulador_de_varios_estados_trazem_a_uf_de_cada_um(
    api_client, activity_rn, rubrica_diarias, municipio_rn, municipio_ce, territory_rn, territory_ce,
):
    from apps.core.tests.factories import RoleFactory, UserFactory

    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    articulador = UserFactory(
        email="articulador.rn.ce@test.com", nome="Articulador RN/CE",
        profiles=[(role, territory_rn), (role, territory_ce)],
    )
    for estado in (municipio_rn.state, municipio_ce.state):
        BudgetAllocationFactory(
            meta=activity_rn.acao.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
            estado=estado, territorio=None, valor_alocado=1_000, valor_comprometido=950,
        )
    api_client.force_authenticate(user=articulador)

    alertas = api_client.get(URL).json()["alertas_saldo"]

    # mesma meta e rubrica nos dois estados: só a UF distingue os alertas
    assert [(a["rubrica_slug"], a["estado_sigla"], a["territorio_id"]) for a in alertas] == [
        ("diarias", "CE", None), ("diarias", "RN", None),
    ]


def test_alertas_do_adt_cobrem_todos_os_territorios_do_perfil(
    api_client, activity_rn, rubrica_diarias, territory_rn, territory_ce,
):
    from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory

    role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
    adt = UserFactory(
        email="adt.rn.ce@test.com", nome="ADT RN/CE", profiles=[(role, territory_rn), (role, territory_ce)],
    )
    nao_vinculado = TerritoryFactory(nome="Território PE", estados=["PE"])
    for territorio in (territory_rn, territory_ce, nao_vinculado):
        BudgetAllocationFactory(
            meta=activity_rn.acao.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.TERRITORIAL,
            territorio=territorio, valor_alocado=1_000, valor_comprometido=950,
        )
    api_client.force_authenticate(user=adt)

    alertas = api_client.get(URL).json()["alertas_saldo"]

    assert {a["territorio_id"] for a in alertas} == {territory_rn.pk, territory_ce.pk}
    assert all(a["nivel"] == "territorial" and a["estado_sigla"] is None for a in alertas)
    assert len(alertas) == 2


# --- sem movimentação --------------------------------------------------------

def test_sem_movimentacao_considera_5_dias_uteis(auth_client_ugp, activity_rn, solicitante_rn):
    parada = _demanda(activity_rn, solicitante_rn, "pre_autorizada", dias_atras=_atras_em_dias_uteis(5))
    _demanda(activity_rn, solicitante_rn, "pre_autorizada", dias_atras=_atras_em_dias_uteis(4))

    bloco = auth_client_ugp.get(URL).json()["sem_movimentacao"]

    assert _ids(bloco) == [parada.pk]
    assert bloco["itens"][0]["dias_uteis_parada"] >= 5


def test_sem_movimentacao_ignora_terminais_e_o_que_nao_e_do_usuario(
    auth_client_ugp, activity_rn, solicitante_rn,
):
    dias = _atras_em_dias_uteis(6)
    _demanda(activity_rn, solicitante_rn, "concluida", dias_atras=dias)
    _demanda(activity_rn, solicitante_rn, "submetida", dias_atras=dias)  # espera o Articulador, não a UGP

    assert auth_client_ugp.get(URL).json()["sem_movimentacao"]["total"] == 0


def test_solicitante_ve_sua_demanda_devolvida_parada(auth_client_solicitante, activity_rn, solicitante_rn):
    devolvida = _demanda(activity_rn, solicitante_rn, "devolvida", dias_atras=_atras_em_dias_uteis(5))

    bloco = auth_client_solicitante.get(URL).json()["sem_movimentacao"]

    assert _ids(bloco) == [devolvida.pk]


# --- performance -------------------------------------------------------------

def _queries_da_chamada(client):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(URL).status_code == 200
    return len(ctx)


def test_dashboard_tem_numero_de_queries_constante_e_responde_em_menos_de_1s(
    auth_client_ugp, activity_rn, solicitante_rn,
):
    for _ in range(10):
        _demanda(activity_rn, solicitante_rn, "pre_autorizada", valor=100, dias_atras=_atras_em_dias_uteis(6))
    queries_pequeno = _queries_da_chamada(auth_client_ugp)

    for _ in range(190):
        _demanda(activity_rn, solicitante_rn, "pre_autorizada", valor=100, dias_atras=_atras_em_dias_uteis(6))

    inicio = time.perf_counter()
    queries_tipico = _queries_da_chamada(auth_client_ugp)
    duracao = time.perf_counter() - inicio

    assert queries_tipico == queries_pequeno
    assert duracao < 1.0
