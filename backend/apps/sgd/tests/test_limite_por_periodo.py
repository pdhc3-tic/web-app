"""As duas travas com o limite por período: a linha nasce do padrão na primeira reserva, e a reserva fica
presa a ela depois da virada."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time

from apps.sgd.services import balance as balance_service
from apps.sgd.services import recurso_extra as recurso_extra_service
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.budget import limites
from apps.sgp.models import BudgetIncreaseRequest, BudgetTransaction, SpendingLimit

pytestmark = pytest.mark.django_db


@pytest.fixture
def padrao_do_perfil(solicitante_rn, rubrica_diarias):
    perfil = solicitante_rn.profiles.get().perfil
    return SpendingLimit.objects.create(
        escopo=SpendingLimit.Escopo.PERFIL, perfil=perfil, rubrica=rubrica_diarias, valor_limite=Decimal("5000"),
        periodo_inicio=date(2026, 1, 1), periodo_fim=limites.FIM_EM_ABERTO,
    )


def _linhas(limite):
    return list(BudgetTransaction.objects.filter(spending_limit=limite).order_by("pk").values_list("tipo", "valor"))


@freeze_time("2026-11-03")
def test_consulta_usa_o_padrao_do_perfil_sem_gravar(
    solicitante_rn, rubrica_diarias, allocation_territorial_rn, padrao_do_perfil,
):
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("1000"),
    )

    assert check.individual.disponivel is True
    assert check.individual.saldo == Decimal("5000")
    assert not SpendingLimit.objects.filter(user=solicitante_rn).exists()


@freeze_time("2026-11-03")
def test_primeira_reserva_cria_a_linha_herdada_e_lanca_no_ledger(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, padrao_do_perfil,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    limite = SpendingLimit.objects.get(user=solicitante_rn)
    assert limite.herdado is True
    assert limite.valor_comprometido == Decimal("1000")
    assert _linhas(limite) == [("reserva", Decimal("1000"))]
    transacao = BudgetTransaction.objects.get(spending_limit=limite)
    assert transacao.demand_request_id == str(demand_request_rn.pk)
    assert transacao.demanda_id == str(demand_request_rn.demanda_id)
    assert transacao.activity_id == demand_request_rn.demanda.activity_id


@freeze_time("2026-11-03")
def test_sem_limite_nem_padrao_a_reserva_e_bloqueada(demand_request_rn, solicitante_rn, allocation_territorial_rn):
    from apps.sgd.exceptions import SaldoInsuficiente

    with pytest.raises(SaldoInsuficiente):
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)


@freeze_time("2026-11-03")
def test_ledger_acompanha_ajuste_e_execucao_com_diferenca(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.ajustar_duas_travas(demand_request=demand_request_rn, novo_valor=Decimal("1200"), usuario=solicitante_rn)
    balance_service.executar_duas_travas(demand_request=demand_request_rn, valor_pago=Decimal("1100"), usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert limite_individual_rn.valor_executado == Decimal("1100")
    assert _linhas(limite_individual_rn) == [
        ("reserva", Decimal("1000")), ("ajuste", Decimal("200")),
        ("execucao", Decimal("1100")), ("liberacao", Decimal("100")),
    ]


@freeze_time("2026-11-03")
def test_ledger_do_limite_nao_interfere_na_idempotencia_do_pool(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("1000")
    assert BudgetTransaction.objects.filter(pool=allocation_territorial_rn, tipo="reserva").count() == 1
    assert BudgetTransaction.objects.filter(spending_limit=limite_individual_rn, tipo="reserva").count() == 1


def test_liberacao_depois_da_virada_sai_da_linha_da_reserva(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, padrao_do_perfil,
):
    with freeze_time("2026-11-03"):
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    linha = SpendingLimit.objects.get(user=solicitante_rn)

    with freeze_time("2027-01-05"):
        demand_request_rn.refresh_from_db()
        balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Cancelada.")

    linha.refresh_from_db()
    assert linha.valor_comprometido == Decimal("0")
    assert SpendingLimit.objects.filter(user=solicitante_rn).count() == 1


def test_execucao_depois_da_virada_sai_da_linha_da_reserva(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, padrao_do_perfil,
):
    with freeze_time("2026-11-03"):
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    linha = SpendingLimit.objects.get(user=solicitante_rn)

    with freeze_time("2027-01-05"):
        demand_request_rn.refresh_from_db()
        balance_service.executar_duas_travas(demand_request=demand_request_rn, valor_pago=Decimal("1000"), usuario=solicitante_rn)

    linha.refresh_from_db()
    assert (linha.valor_comprometido, linha.valor_executado) == (Decimal("0"), Decimal("1000"))


def test_nova_reserva_depois_da_virada_usa_o_periodo_novo(
    demand_request_rn, solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn, padrao_do_perfil,
):
    with freeze_time("2026-11-03"):
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    outra = DemandRequestFactory(
        demanda=DemandFactory(activity=activity_rn, solicitante=solicitante_rn),
        tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("700"),
    )

    with freeze_time("2027-01-05"):
        balance_service.reservar_duas_travas(demand_request=outra, usuario=solicitante_rn)

    novo = SpendingLimit.objects.get(user=solicitante_rn, periodo_inicio=date(2027, 1, 1))
    assert novo.valor_comprometido == Decimal("700")
    assert SpendingLimit.objects.get(user=solicitante_rn, periodo_inicio=date(2026, 10, 1)).valor_comprometido == Decimal("1000")


@freeze_time("2026-11-03")
def test_recurso_extra_eleva_a_linha_herdada_e_ela_vira_sobrescrita(
    usuario_ugp, solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn, padrao_do_perfil,
):
    limite = limites.travar_limite_vigente(user_id=solicitante_rn.pk, rubrica_id=rubrica_diarias.pk, criar=True)
    pedido = BudgetIncreaseRequest.objects.create(
        user=solicitante_rn, rubrica=rubrica_diarias, valor_solicitado=Decimal("800"), activity=activity_rn,
        justificativa="Mutirão.", status="com_parecer",
    )

    recurso_extra_service.decidir(pedido, usuario=usuario_ugp, decisao="aprovar", justificativa="Aprovado.")

    limite.refresh_from_db()
    assert limite.valor_limite == Decimal("5800")
    assert limite.herdado is False
    assert limite.justificativa.startswith(f"Recurso extra #{pedido.pk}")
    assert _linhas(limite) == [("aumento_limite", Decimal("800"))]


@freeze_time("2026-11-03")
def test_recurso_extra_sem_limite_cria_a_linha_do_periodo(
    usuario_ugp, solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn,
):
    pedido = BudgetIncreaseRequest.objects.create(
        user=solicitante_rn, rubrica=rubrica_diarias, valor_solicitado=Decimal("800"), activity=activity_rn,
        justificativa="Mutirão.", status="com_parecer",
    )

    recurso_extra_service.decidir(pedido, usuario=usuario_ugp, decisao="aprovar", justificativa="Aprovado.")

    limite = SpendingLimit.objects.get(user=solicitante_rn, rubrica=rubrica_diarias)
    assert limite.valor_limite == Decimal("800")
    assert limite.periodo_inicio == date(2026, 10, 1)


@freeze_time("2026-11-03")
def test_valor_faltante_usa_o_limite_efetivo(demand_rascunho_rn, demand_request_rn, rubrica_diarias, padrao_do_perfil):
    SpendingLimit.objects.filter(pk=padrao_do_perfil.pk).update(valor_limite=Decimal("600"))

    assert recurso_extra_service.deficit_individual(demand_rascunho_rn, rubrica_diarias) == Decimal("400")


@freeze_time("2026-11-03")
def test_trilha_da_demanda_le_o_nome_antigo_e_o_novo_da_entidade(auth_client_ugp, demand_request_rn):
    from apps.core.models.audit_log import AuditLog

    pedido = BudgetIncreaseRequest.objects.create(
        user=demand_request_rn.demanda.solicitante, rubrica=demand_request_rn.rubrica,
        valor_solicitado=Decimal("10"), demanda_id=str(demand_request_rn.demanda_id), justificativa="x",
    )
    for entidade in ("DemandIndividualLimit", "SpendingLimit"):
        AuditLog.objects.create(
            acao="aumento_limite", modulo="sgd", entidade=entidade, entidade_id="1",
            valores_novos={"pedido": pedido.pk},
        )

    from apps.core.tests.factories import RoleFactory, UserFactory

    auth_client_ugp.force_authenticate(user=UserFactory(profiles=[(RoleFactory(slug="super-admin", nome="Super Admin"), None)]))
    resposta = auth_client_ugp.get(f"/api/v1/sgd/demandas/{demand_request_rn.demanda_id}/auditoria/")

    assert resposta.status_code == 200
    eventos = resposta.data["results"] if isinstance(resposta.data, dict) else resposta.data
    assert sum(1 for evento in eventos if evento["acao"] == "aumento_limite") == 2


def _demanda_com_reservas_em_dois_periodos(activity_rn, solicitante_rn, rubrica_diarias, status="devolvida"):
    """Uma solicitação reservada no trimestre passado e outra ainda sem reserva."""
    demanda = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status=status)
    antiga = DemandRequestFactory(demanda=demanda, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("100"))
    nova = DemandRequestFactory(demanda=demanda, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("200"))
    with freeze_time("2026-11-03"):
        balance_service.reservar_duas_travas(demand_request=antiga, usuario=solicitante_rn)
    return demanda, antiga, nova


def test_submissao_trava_as_linhas_dos_dois_periodos_antes_do_pool(
    activity_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, padrao_do_perfil,
):
    demanda, antiga, nova = _demanda_com_reservas_em_dois_periodos(activity_rn, solicitante_rn, rubrica_diarias)

    with freeze_time("2027-01-05"), CaptureQueriesContext(connection) as consultas, transaction.atomic():
        for solicitacao in balance_service.na_ordem_de_lock([antiga, nova], criar=True):
            balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=solicitante_rn, adiar_gravacao=True)

    sqls = [q["sql"] for q in consultas]
    primeira_trava_de_pool = next(i for i, sql in enumerate(sqls) if "FOR UPDATE" in sql and '"sgp_budgetpool"' in sql)
    trava_do_lote = next(i for i, sql in enumerate(sqls) if "FOR UPDATE" in sql and '"sgp_spendinglimit"' in sql)
    criacao_da_linha_nova = next(i for i, sql in enumerate(sqls) if sql.startswith('INSERT INTO "sgp_spendinglimit"'))
    # A linha da reserva antiga e a do período novo ficam travadas antes de qualquer pool.
    assert f"'{antiga.pk}'" in sqls[trava_do_lote]
    assert trava_do_lote < primeira_trava_de_pool
    assert criacao_da_linha_nova < primeira_trava_de_pool
    assert SpendingLimit.objects.filter(user=solicitante_rn).count() == 2


def test_na_ordem_de_lock_trava_rubrica_a_rubrica(
    activity_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetRubricaFactory

    outra = BudgetRubricaFactory()
    demanda = DemandFactory(activity=activity_rn, solicitante=solicitante_rn)
    primeira = DemandRequestFactory(demanda=demanda, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("1"))
    segunda = DemandRequestFactory(demanda=demanda, tipo="diaria", rubrica=outra, valor_estimado=Decimal("1"))
    solicitacoes = sorted([primeira, segunda], key=lambda s: s.rubrica_id)

    travadas = []
    with CaptureQueriesContext(connection) as consultas, transaction.atomic():
        for solicitacao in balance_service.na_ordem_de_lock(solicitacoes):
            travadas.append(sum(1 for q in consultas if "FOR UPDATE" in q["sql"] and '"sgp_spendinglimit"' in q["sql"]))

    # Uma trava de limite ao entrar em cada rubrica: nunca as duas de uma vez, antes dos pools.
    assert travadas == [1, 2]
