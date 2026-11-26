from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time

from apps.core.models.notifications import TipoNotificacao
from apps.core.models.system_config import SystemConfig
from apps.core.models import Territory
from apps.core.tests.factories import TerritoryFactory
from apps.sgd.models import Demand
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.budget import alertas
from apps.sgp.models import BudgetAlert, BudgetPool, BudgetTransaction, TEDVersionRubrica, WorkPlanAcao
from apps.sgp.tasks import check_budget_return_risk, check_budget_underexecution
from apps.sgp.ted import projecoes
from apps.sgp.ted.services import gerar_snapshot_do_plano
from apps.sgp.tests.factories import (
    ActivityFactory,
    BudgetPoolFactory,
    BudgetRubricaFactory,
    BudgetTransactionFactory,
    IndicatorFactory,
    TEDVersionFactory,
    UFPAFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
    WorkPlanSubmetaFactory,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgp/ted/"
CURVA = f"{URL}curva-s/"
PROJECOES = f"{URL}projecoes/"
RANKING = f"{URL}ranking-territorios/"
Escopo = projecoes.EscopoDaCurva
Nivel = BudgetPool.Nivel
Tipo = BudgetTransaction.Tipo
PARAMETROS = (
    "budget_return_risk_alert_months", "budget_return_risk_pct", "budget_subexec_alert_months",
    "budget_subexec_min_pct",
)
EMAIL_E_IN_APP = {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}


@pytest.fixture(autouse=True)
def sem_envio_de_email():
    with patch("apps.core.tasks.notifications.send_email_notification.delay"):
        yield


@pytest.fixture(autouse=True)
def parametros_sem_cache():
    """O cache de `get_config` não volta com o rollback do teste."""
    cache.delete_many([f"system_config:{chave}" for chave in PARAMETROS])
    yield
    cache.delete_many([f"system_config:{chave}" for chave in PARAMETROS])


def _config(chave, valor):
    SystemConfig.objects.update_or_create(chave=chave, defaults={"valor": str(valor), "tipo": "integer"})
    cache.delete(f"system_config:{chave}")


def _momento(ano, mes, dia):
    return timezone.make_aware(datetime(ano, mes, dia, 12, 0))


def _concluida(acao, municipio, quando):
    return ActivityFactory(acao=acao, municipio=municipio, status="concluido", data_inicio=quando, data_fim=quando)


def _paga(atividade, rubrica, valor, quando):
    demanda = DemandFactory(activity=atividade, status="concluida")
    Demand.objects.filter(pk=demanda.pk).update(status_alterado_em=quando)
    return DemandRequestFactory(demanda=demanda, rubrica=rubrica, valor_pago=Decimal(valor))


@pytest.fixture
def diarias():
    return BudgetRubricaFactory(slug="diarias-projecoes", nome="Diárias")


@pytest.fixture
def plano(db):
    """Ação 1.1.1: 10 oficinas a R$ 100, de 1º/jan a 30/abr de 2026 (120 dias)."""
    meta = WorkPlanMetaFactory(numero=1, titulo="Meta 1")
    submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1", titulo="Formação")
    return WorkPlanAcaoFactory(
        meta=meta, submeta=submeta, numero="1.1.1", indicador=IndicatorFactory(),
        quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 4, 30),
    )


def _versao(**campos):
    return TEDVersionFactory(**{
        "vigencia_inicio": date(2026, 1, 1), "vigencia_fim": date(2026, 12, 31), "valor_global": Decimal("1000"),
        "plano_snapshot": gerar_snapshot_do_plano(), **campos,
    })


@pytest.fixture
def versao(plano):
    return _versao()


@pytest.fixture
def execucao_fev_mar(plano, versao, municipio_rn, diarias):
    """2 oficinas e R$ 200 em fevereiro; 1 oficina e R$ 100 em março."""
    fevereiro = [_concluida(plano, municipio_rn, _momento(2026, 2, 10)) for _ in range(2)]
    marco = _concluida(plano, municipio_rn, _momento(2026, 3, 20))
    _paga(fevereiro[0], diarias, "200", _momento(2026, 2, 15))
    _paga(marco, diarias, "100", _momento(2026, 3, 25))


def _ponto(curva, mes):
    return next(p for p in curva.pontos if p.mes == date(2026, mes, 1))


# ---------------------------------------------------------------------------
# Curva S
# ---------------------------------------------------------------------------

class TestCurvaS:
    def test_previsto_distribuido_por_dia_entre_o_inicio_e_o_fim_da_acao(self, usuario, versao):
        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 3, 15))

        assert len(curva.pontos) == 12
        assert [(p.previsto_quantidade, p.previsto_valor) for p in curva.pontos[:5]] == [
            (Decimal("2.58"), Decimal("258.33")),
            (Decimal("4.92"), Decimal("491.67")),
            (Decimal("7.50"), Decimal("750.00")),
            (Decimal("10.00"), Decimal("1000.00")),
            (Decimal("10.00"), Decimal("1000.00")),
        ]
        assert _ponto(curva, 12).previsto_valor == Decimal("1000.00")

    def test_previsto_fecha_no_ultimo_mes_quando_a_acao_passa_da_vigencia(self, usuario, plano):
        versao = _versao(vigencia_fim=date(2026, 3, 31))

        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 3, 15))

        assert [(p.previsto_quantidade, p.previsto_valor) for p in curva.pontos] == [
            (Decimal("2.58"), Decimal("258.33")),
            (Decimal("4.92"), Decimal("491.67")),
            (Decimal("10.00"), Decimal("1000.00")),
        ]

    def test_realizado_acumulado_para_no_mes_corrente(self, usuario, versao, execucao_fev_mar):
        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 3, 15))

        assert [(p.realizado_quantidade, p.realizado_valor) for p in curva.pontos[:4]] == [
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("2.00"), Decimal("200.00")),
            (Decimal("3.00"), Decimal("300.00")),
            (None, None),
        ]

    @freeze_time("2026-03-15 12:00")
    def test_termino_futuro_entra_no_mes_corrente(self, auth_client, plano, versao, execucao_fev_mar,
                                                   municipio_rn):
        _concluida(plano, municipio_rn, _momento(2026, 5, 10))

        marco = auth_client.get(CURVA).data["pontos"][2]
        aderencia = auth_client.get(f"{URL}aderencia/", {"escopo": "projeto"}).data["results"][0]

        assert marco["realizado_quantidade"] == aderencia["quantidade_realizada"] == "4.00"

    @freeze_time("2026-12-31 12:00")
    def test_acumulado_fecha_com_a_aderencia(self, auth_client, versao, execucao_fev_mar):
        ultimo = auth_client.get(CURVA).data["pontos"][-1]
        aderencia = auth_client.get(f"{URL}aderencia/", {"escopo": "projeto"}).data["results"][0]

        assert (ultimo["realizado_quantidade"], ultimo["realizado_valor"]) == (
            aderencia["quantidade_realizada"], aderencia["valor_executado"],
        )

    def test_ufpa_conta_no_mes_da_primeira_atividade(self, usuario, municipio_rn):
        meta = WorkPlanMetaFactory(numero=2)
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="2.1")
        acao = WorkPlanAcaoFactory(
            meta=meta, submeta=submeta, numero="2.1.1", indicador=IndicatorFactory(forma_apuracao="soma_ufpas"),
            quantidade_planejada=Decimal("5"), valor_unitario=Decimal("10"),
        )
        versao = _versao()
        repetida, nova = UFPAFactory(municipio=municipio_rn), UFPAFactory(municipio=municipio_rn)
        _concluida(acao, municipio_rn, _momento(2026, 2, 10)).ufpas_participantes.set([repetida])
        _concluida(acao, municipio_rn, _momento(2026, 3, 10)).ufpas_participantes.set([repetida, nova])

        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 3, 31))

        assert (_ponto(curva, 2).realizado_quantidade, _ponto(curva, 3).realizado_quantidade) == (
            Decimal("1.00"), Decimal("2.00"),
        )

    def test_acao_manual_entra_no_valor_e_fica_fora_da_quantidade(self, usuario, plano):
        WorkPlanAcaoFactory(
            meta=plano.meta, submeta=plano.submeta, numero="1.1.2", indicador=IndicatorFactory(forma_apuracao="manual"),
            quantidade_planejada=Decimal("5"), valor_unitario=Decimal("10"), quantidade_realizada=5,
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 4, 30),
        )
        versao = _versao()

        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 6, 1))

        assert (_ponto(curva, 4).previsto_quantidade, _ponto(curva, 4).previsto_valor) == (
            Decimal("10.00"), Decimal("1050.00"),
        )
        assert curva.acoes_manuais_fora_da_quantidade == 1

    def test_por_meta_considera_so_as_acoes_dela(self, auth_client, plano, municipio_rn):
        outra_meta = WorkPlanMetaFactory(numero=3)
        WorkPlanAcaoFactory(
            meta=outra_meta, submeta=WorkPlanSubmetaFactory(meta=outra_meta, numero="3.1"), numero="3.1.1",
            quantidade_planejada=Decimal("50"), valor_unitario=Decimal("1"),
        )
        _versao()

        resposta = auth_client.get(CURVA, {"escopo": "meta", "referencia_id": plano.meta_id})

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["nome"] == "Meta 1 — Meta 1"
        assert resposta.data["pontos"][-1]["previsto_quantidade"] == "10.00"

    @freeze_time("2026-02-10 12:00")
    def test_por_rubrica_so_em_reais(self, auth_client, versao, diarias):
        TEDVersionRubrica.objects.create(versao=versao, rubrica=diarias, valor_aprovado=Decimal("1200"))
        pool = BudgetPoolFactory(rubrica=diarias, nivel=Nivel.NACIONAL, estado=None, territorio=None)
        with freeze_time("2026-01-20 12:00"):
            BudgetTransactionFactory(pool=pool, tipo=Tipo.EXECUCAO, valor=Decimal("100"))

        resposta = auth_client.get(CURVA, {"escopo": "rubrica", "referencia_id": diarias.pk})

        assert resposta.status_code == 200, resposta.data
        janeiro, fevereiro, marco = resposta.data["pontos"][:3]
        assert (janeiro["previsto_valor"], janeiro["realizado_valor"], janeiro["previsto_quantidade"]) == (
            "101.92", "100.00", None,
        )
        assert (fevereiro["realizado_valor"], marco["realizado_valor"]) == ("100.00", None)
        assert resposta.data["ritmo_necessario"]["quantidade_por_mes"] is None

    def test_ritmo_necessario(self, usuario, versao, execucao_fev_mar):
        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2026, 7, 1))

        assert curva.ritmo_necessario == projecoes.RitmoNecessario(
            Decimal("6.01"), Decimal("1.16"), Decimal("116.43"),
        )

    def test_sem_ritmo_necessario_depois_da_vigencia(self, usuario, versao):
        curva = projecoes.curva_s(usuario, Escopo.PROJETO, versao, hoje=date(2027, 1, 10))

        assert curva.ritmo_necessario == projecoes.RitmoNecessario(None, None, None)

    def test_versao_anterior_usa_o_snapshot_dela(self, auth_client, plano, versao):
        WorkPlanAcao.objects.filter(pk=plano.pk).update(quantidade_planejada=Decimal("20"))
        _versao(ted=versao.ted, numero_versao=2, tipo="aditivo")

        anterior = auth_client.get(CURVA, {"versao": versao.pk}).data
        vigente = auth_client.get(CURVA).data

        assert (anterior["versao"]["numero_versao"], anterior["pontos"][-1]["previsto_quantidade"]) == (1, "10.00")
        assert (vigente["versao"]["numero_versao"], vigente["pontos"][-1]["previsto_quantidade"]) == (2, "20.00")

    def test_articulador_ve_o_realizado_dos_seus_estados(
        self, request, plano, versao, municipio_rn, municipio_ce, diarias,
    ):
        _paga(_concluida(plano, municipio_rn, _momento(2026, 2, 10)), diarias, "100", _momento(2026, 2, 15))
        _paga(_concluida(plano, municipio_ce, _momento(2026, 2, 10)), diarias, "300", _momento(2026, 2, 15))
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        with freeze_time("2026-02-28 12:00"):
            resposta = cliente.get(CURVA).data

        fevereiro = resposta["pontos"][1]
        assert (fevereiro["realizado_quantidade"], fevereiro["realizado_valor"]) == ("1.00", "100.00")
        assert (resposta["ritmo_necessario"]["quantidade_por_mes"], resposta["ritmo_necessario"]["valor_por_mes"]) == (
            None, None,
        )

    def test_curva_da_rubrica_e_so_da_leitura_nacional(self, request, versao, diarias):
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        resposta = cliente.get(CURVA, {"escopo": "rubrica", "referencia_id": diarias.pk})

        assert resposta.status_code == 403

    def test_referencia_obrigatoria_fora_do_projeto(self, auth_client, versao):
        resposta = auth_client.get(CURVA, {"escopo": "submeta"})

        assert resposta.status_code == 400
        assert "referencia_id" in resposta.data

    def test_referencia_inexistente(self, auth_client, versao):
        resposta = auth_client.get(CURVA, {"escopo": "meta", "referencia_id": 999999})

        assert (resposta.status_code, resposta.data["code"]) == (400, "referencia_invalida")


# ---------------------------------------------------------------------------
# Projeções por rubrica
# ---------------------------------------------------------------------------

def _nacional(rubrica, *, comprometido="0", executado="0"):
    return BudgetPoolFactory(
        rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=Decimal("1000"),
        valor_comprometido=Decimal(comprometido), valor_executado=Decimal(executado),
    )


def _lancar(pool, tipo, valor, dia):
    with freeze_time(f"{dia} 12:00"):
        return BudgetTransactionFactory(pool=pool, tipo=tipo, valor=Decimal(valor))


@pytest.fixture
def aprovado(versao, diarias):
    """R$ 1.000 aprovados para Diárias na versão vigente, de 1º/jan a 31/dez de 2026."""
    TEDVersionRubrica.objects.create(versao=versao, rubrica=diarias, valor_aprovado=Decimal("1000"))
    return versao


@pytest.fixture
def ritmo_de_referencia(aprovado, diarias):
    """Executado R$ 300 e comprometido R$ 100. Na janela de 90 dias até 1º/jul: R$ 270
    executados (3/dia) e R$ 360 comprometidos (4/dia)."""
    pool = _nacional(diarias, comprometido="100", executado="300")
    _lancar(pool, Tipo.EXECUCAO, "270", "2026-05-10")
    _lancar(pool, Tipo.RESERVA, "450", "2026-04-10")
    _lancar(pool, Tipo.LIBERACAO, "90", "2026-06-10")
    _lancar(pool, Tipo.EXECUCAO, "30", "2026-03-01")
    return pool


class TestProjecoes:
    def test_projecao_com_dados_de_referencia(self, ritmo_de_referencia):
        resultado = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1))

        linha = resultado.rubricas[0]
        assert (resultado.janela_inicio, resultado.janela_dias) == (date(2026, 4, 2), 90)
        assert (linha.ritmo_execucao_mensal, linha.ritmo_comprometimento_mensal) == (
            Decimal("91.31"), Decimal("121.75"),
        )
        assert (linha.valor_executado_projetado, linha.perc_execucao_projetado) == (
            Decimal("849.00"), Decimal("84.90"),
        )
        assert (linha.saldo_remanescente_projetado, linha.perc_saldo_remanescente_projetado) == (
            Decimal("151.00"), Decimal("15.10"),
        )
        assert (linha.data_esgotamento, linha.esgota_antes_do_fim, linha.ja_esgotada) == (
            date(2026, 11, 28), True, False,
        )
        assert linha.ritmo_necessario_mensal == Decimal("116.43")
        assert linha.risco_devolucao is True

    def test_limiar_do_saldo_remanescente(self, ritmo_de_referencia):
        _config("budget_return_risk_pct", 20)

        resultado = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1))

        assert (resultado.limiar_saldo_remanescente_pct, resultado.rubricas[0].risco_devolucao) == (
            Decimal("20"), False,
        )

    def test_pagamento_acima_do_reservado_entra_no_ritmo_de_comprometimento(self, aprovado, diarias):
        pool = _nacional(diarias)
        _lancar(pool, Tipo.RESERVA, "100", "2026-05-01")
        with freeze_time("2026-05-10 12:00"):
            BudgetTransactionFactory(
                pool=pool, tipo=Tipo.EXECUCAO, valor=Decimal("150"),
                saldo_anterior=Decimal("500"), saldo_posterior=Decimal("450"),
            )

        linha = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).rubricas[0]

        assert linha.ritmo_comprometimento_mensal == Decimal("50.73")

    def test_contra_uma_versao_anterior(self, auth_client, aprovado, diarias):
        nova = _versao(ted=aprovado.ted, numero_versao=2, tipo="aditivo")
        TEDVersionRubrica.objects.create(versao=nova, rubrica=diarias, valor_aprovado=Decimal("2000"))

        vigente = auth_client.get(PROJECOES).data
        anterior = auth_client.get(PROJECOES, {"versao": aprovado.pk}).data

        assert (vigente["versao"]["numero_versao"], vigente["rubricas"][0]["valor_aprovado"]) == (2, "2000.00")
        assert (anterior["versao"]["numero_versao"], anterior["rubricas"][0]["valor_aprovado"]) == (1, "1000.00")

    def test_janela_tem_noventa_dias(self, aprovado, diarias):
        pool = _nacional(diarias)
        _lancar(pool, Tipo.EXECUCAO, "90", "2026-04-02")
        _lancar(pool, Tipo.EXECUCAO, "180", "2026-04-03")

        linha = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).rubricas[0]

        assert linha.ritmo_execucao_mensal == Decimal("60.88")

    def test_vigencia_recente_usa_o_tempo_decorrido(self, plano, diarias):
        versao = _versao(vigencia_inicio=date(2026, 6, 1))
        TEDVersionRubrica.objects.create(versao=versao, rubrica=diarias, valor_aprovado=Decimal("1000"))
        _lancar(_nacional(diarias), Tipo.EXECUCAO, "300", "2026-06-15")

        resultado = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1))

        assert (resultado.janela_inicio, resultado.janela_dias) == (date(2026, 6, 1), 30)
        assert resultado.rubricas[0].ritmo_execucao_mensal == Decimal("304.38")

    def test_sem_ritmo_nao_ha_data_de_esgotamento(self, aprovado, diarias):
        _nacional(diarias, executado="100")

        linha = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).rubricas[0]

        assert (linha.data_esgotamento, linha.esgota_antes_do_fim) == (None, False)
        assert (linha.perc_execucao_projetado, linha.risco_devolucao) == (Decimal("10.00"), True)

    def test_rubrica_ja_esgotada(self, aprovado, diarias):
        _nacional(diarias, comprometido="400", executado="600")

        linha = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).rubricas[0]

        assert (linha.ja_esgotada, linha.esgota_antes_do_fim, linha.data_esgotamento) == (True, True, None)

    def test_soma_todos_os_pools_da_rubrica(self, aprovado, diarias, territory_rn):
        _nacional(diarias, executado="100")
        BudgetPoolFactory(
            rubrica=diarias, territorio=territory_rn, valor_alocado=Decimal("200"), valor_executado=Decimal("200"),
        )

        assert projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).rubricas[0].valor_executado == Decimal("300.00")

    def test_linha_do_projeto_soma_as_rubricas(self, aprovado, diarias):
        material = BudgetRubricaFactory(slug="material-projecoes", nome="Material")
        TEDVersionRubrica.objects.create(versao=aprovado, rubrica=material, valor_aprovado=Decimal("3000"))
        _nacional(diarias, executado="100")
        _nacional(material, executado="900")

        projeto = projecoes.projecoes_por_rubrica(hoje=date(2026, 7, 1)).projeto

        assert (projeto.nome, projeto.rubrica_id, projeto.valor_aprovado, projeto.valor_executado) == (
            "Projeto", None, Decimal("4000.00"), Decimal("1000.00"),
        )
        assert projeto.perc_execucao_atual == Decimal("25.00")

    @freeze_time("2026-07-01 12:00")
    @pytest.mark.parametrize("cliente", ["auth_client", "auth_client_super_admin", "auth_client_fgd"])
    def test_leitura_nacional(self, request, cliente, ritmo_de_referencia):
        resposta = request.getfixturevalue(cliente).get(PROJECOES)

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["rubricas"][0]["perc_execucao_projetado"] == "84.90"
        assert (resposta.data["alerta_a_partir_de"], resposta.data["na_janela_do_alerta"]) == ("2025-12-31", True)
        assert (resposta.data["antecedencia_meses"], resposta.data["limiar_saldo_remanescente_pct"]) == (12, "10.00")

    def test_articulador_nao_le_o_agregado_de_todos_os_estados(self, request, ritmo_de_referencia, territory_rn):
        BudgetPoolFactory(
            rubrica=ritmo_de_referencia.rubrica, territorio=territory_rn,
            valor_alocado=Decimal("200"), valor_executado=Decimal("200"),
        )

        resposta = request.getfixturevalue("auth_client_articulador_rn").get(PROJECOES)

        assert resposta.status_code == 403

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_sem_acesso"])
    @pytest.mark.parametrize("rota", [PROJECOES, CURVA, RANKING])
    def test_perfis_fora_do_ted_recebem_403(self, request, cliente, rota, aprovado):
        assert request.getfixturevalue(cliente).get(rota).status_code == 403

    @pytest.mark.parametrize("rota", [PROJECOES, CURVA, RANKING])
    def test_sem_ted_cadastrado(self, auth_client, rota):
        resposta = auth_client.get(rota)

        assert (resposta.status_code, resposta.data["code"]) == (400, "ted_nao_cadastrado")


# ---------------------------------------------------------------------------
# Alerta de risco de devolução
# ---------------------------------------------------------------------------

def _canais(usuario):
    return set(usuario.notifications.filter(evento=alertas.EVENTO_RISCO_DEVOLUCAO).values_list("tipo", flat=True))


class TestRiscoDeDevolucao:
    @pytest.fixture
    def sem_ritmo(self, aprovado, diarias):
        """R$ 100 executados de R$ 1.000 e nada na janela: projeção de 10 %."""
        return _nacional(diarias, executado="100")

    @pytest.mark.parametrize("hoje,abre", [("2026-06-29", False), ("2026-06-30", True), ("2026-07-01", True)])
    def test_abre_a_partir_da_antecedencia(self, sem_ritmo, usuario, hoje, abre):
        _config("budget_return_risk_alert_months", 6)

        with freeze_time(f"{hoje} 12:00"):
            check_budget_return_risk()

        assert BudgetAlert.objects.filter(tipo=BudgetAlert.Tipo.RISCO_DEVOLUCAO, faixa="devolucao").exists() is abre
        assert _canais(usuario) == (EMAIL_E_IN_APP if abre else set())

    @freeze_time("2026-03-02 12:00")
    def test_avisa_antes_da_subexecucao(self, sem_ritmo, usuario):
        """Com os padrões, 12 meses contra 6: em março a subexecução ainda não avalia."""
        check_budget_return_risk()
        check_budget_underexecution()

        assert set(BudgetAlert.objects.values_list("tipo", flat=True)) == {BudgetAlert.Tipo.RISCO_DEVOLUCAO}

    @freeze_time("2026-07-01 12:00")
    def test_alerta_no_pool_nacional_com_o_saldo_projetado(self, sem_ritmo, usuario):
        check_budget_return_risk()

        alerta = BudgetAlert.objects.get(tipo=BudgetAlert.Tipo.RISCO_DEVOLUCAO)
        assert (alerta.escopo, alerta.referencia_id, alerta.rubrica_id) == ("pool", sem_ritmo.pk, sem_ritmo.rubrica_id)
        assert alerta.percentual_atingido == Decimal("90.00")
        assert alerta.usuarios_alertados_ids == [usuario.pk]

    @freeze_time("2026-07-01 12:00")
    def test_nao_duplica_e_resolve_quando_o_ritmo_sobe(self, sem_ritmo, usuario):
        check_budget_return_risk()
        total = usuario.notifications.count()
        assert check_budget_return_risk() == 0
        assert usuario.notifications.count() == total

        _lancar(sem_ritmo, Tipo.EXECUCAO, "450", "2026-06-15")
        check_budget_return_risk()

        assert BudgetAlert.objects.get(tipo=BudgetAlert.Tipo.RISCO_DEVOLUCAO).resolvido_em is not None

    @freeze_time("2026-07-01 12:00")
    def test_projecao_refeita_com_o_pool_travado(self, sem_ritmo, usuario):
        travar = alertas._travar

        def executa_enquanto_espera(modelo, pk):
            _lancar(sem_ritmo, Tipo.EXECUCAO, "450", "2026-06-15")
            return travar(modelo, pk)

        with patch.object(alertas, "_travar", side_effect=executa_enquanto_espera):
            check_budget_return_risk()

        assert not BudgetAlert.objects.exists()

    def test_resolve_depois_do_fim_da_vigencia(self, sem_ritmo, usuario):
        with freeze_time("2026-07-01 12:00"):
            check_budget_return_risk()
        with freeze_time("2027-01-05 12:00"):
            check_budget_return_risk()

        assert BudgetAlert.objects.get(tipo=BudgetAlert.Tipo.RISCO_DEVOLUCAO).resolvido_em is not None

    @freeze_time("2025-12-31 12:00")
    def test_nao_avalia_antes_do_inicio_da_vigencia(self, sem_ritmo, usuario):
        """Vigência de 12 meses e antecedência de 12: a janela começaria antes do TED."""
        check_budget_return_risk()

        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-07-01 12:00")
    def test_parametros_proprios_no_core(self, sem_ritmo, usuario):
        _config("budget_return_risk_pct", 95)
        check_budget_return_risk()
        assert not BudgetAlert.objects.exists()

        _config("budget_return_risk_pct", 10)
        _config("budget_return_risk_alert_months", 1)
        check_budget_return_risk()
        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-07-01 12:00")
    def test_parametro_fora_da_faixa_vale_o_padrao(self, sem_ritmo, usuario):
        _config("budget_return_risk_pct", 0)

        check_budget_return_risk()

        assert BudgetAlert.objects.filter(tipo=BudgetAlert.Tipo.RISCO_DEVOLUCAO).exists()

    @pytest.mark.parametrize("chave, valor, aceito", [
        ("budget_return_risk_pct", 0, False),
        ("budget_return_risk_pct", 101, False),
        ("budget_return_risk_pct", 15, True),
        ("budget_return_risk_alert_months", 25, False),
        ("budget_return_risk_alert_months", 18, True),
    ])
    def test_parametros_validados_no_system_config(self, auth_client_super_admin, chave, valor, aceito):
        resposta = auth_client_super_admin.patch(f"/api/v1/system-config/{chave}/", {"valor": valor}, format="json")

        assert resposta.status_code == (200 if aceito else 400), resposta.data

    @freeze_time("2026-07-01 12:00")
    def test_sem_ted_nao_avalia(self, diarias, usuario):
        _nacional(diarias, executado="100")

        assert check_budget_return_risk() == 0
        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-10-01 12:00")
    def test_subexecucao_usa_o_fim_da_vigencia_do_ted(self, sem_ritmo, usuario):
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2028, 12, 31))

        check_budget_underexecution()

        assert BudgetAlert.objects.filter(tipo=BudgetAlert.Tipo.SUBEXECUCAO).exists()

    def test_agenda_semanal(self):
        agenda = settings.CELERY_BEAT_SCHEDULE["check_budget_return_risk"]

        assert agenda["task"] == "sgp.tasks.check_budget_return_risk"
        assert (agenda["schedule"].day_of_week, agenda["schedule"].hour, agenda["schedule"].minute) == (
            {1}, {3}, {15},
        )

    @freeze_time("2026-07-01 12:00")
    def test_aparece_na_lista_de_alertas(self, auth_client, sem_ritmo):
        check_budget_return_risk()

        resposta = auth_client.get("/api/v1/sgp/orcamento/alertas/", {"tipo": "risco_devolucao"})

        assert resposta.status_code == 200, resposta.data
        assert [a["tipo"] for a in resposta.data["results"]] == ["risco_devolucao"]


# ---------------------------------------------------------------------------
# Ranking por território
# ---------------------------------------------------------------------------

@pytest.fixture
def execucao_rn(plano, versao, municipio_rn, diarias):
    """5 oficinas concluídas no RN e R$ 400 pagos."""
    atividades = [_concluida(plano, municipio_rn, _momento(2026, 3, 1)) for _ in range(5)]
    _paga(atividades[0], diarias, "400", _momento(2026, 3, 5))


def _por_territorio(resposta):
    assert resposta.status_code == 200, resposta.data
    return {linha["referencia_id"]: linha for linha in resposta.data["results"]}


class TestRanking:
    def test_territorio_sem_execucao_entra_zerado(self, auth_client, execucao_rn, territory_rn, territory_ce):
        linhas = _por_territorio(auth_client.get(RANKING))

        rn, ce = linhas[territory_rn.pk], linhas[territory_ce.pk]
        assert (rn["perc_fisico"], rn["perc_financeiro"], rn["posicao_fisico"], rn["posicao_financeiro"]) == (
            "50.00", "40.00", 1, 1,
        )
        assert (ce["perc_fisico"], ce["indice"], ce["faixa"], ce["posicao_fisico"]) == ("0.00", None, None, 2)

    def test_empatados_dividem_a_posicao(self, auth_client, execucao_rn, territory_rn, territory_ce):
        terceiro = TerritoryFactory(nome="Território PB", estados=["PB"])

        linhas = _por_territorio(auth_client.get(RANKING))

        assert [linhas[t.pk]["posicao_fisico"] for t in (territory_rn, territory_ce, terceiro)] == [1, 2, 2]

    def test_ordenar_pelo_financeiro(self, auth_client, plano, versao, municipio_rn, municipio_ce, diarias,
                                     territory_rn, territory_ce):
        _concluida(plano, municipio_rn, _momento(2026, 3, 1))
        for _ in range(3):
            _concluida(plano, municipio_ce, _momento(2026, 3, 1))
        _paga(_concluida(plano, municipio_rn, _momento(2026, 3, 1)), diarias, "800", _momento(2026, 3, 5))

        def primeiro(**params):
            return auth_client.get(RANKING, params).data["results"][0]["referencia_id"]

        assert (primeiro(), primeiro(ordenar="financeiro")) == (territory_ce.pk, territory_rn.pk)

    def test_articulador_ve_so_os_territorios_dos_seus_estados(
        self, request, execucao_rn, territory_rn, territory_ce,
    ):
        linhas = _por_territorio(request.getfixturevalue("auth_client_articulador_rn").get(RANKING))

        assert territory_rn.pk in linhas
        assert territory_ce.pk not in linhas

    def test_ranking_nao_aceita_recorte_por_territorio(self, auth_client, execucao_rn, territory_rn):
        resposta = auth_client.get(RANKING, {"territorio_id": territory_rn.pk})

        assert resposta.status_code == 400
        assert "territorio_id" in resposta.data

    def test_todos_os_territorios_sem_paginacao(self, auth_client, execucao_rn):
        for numero in range(16):
            TerritoryFactory(nome=f"Território {numero:02d}", estados=["PB"])

        resposta = auth_client.get(RANKING)

        assert resposta.status_code == 200, resposta.data
        assert len(resposta.data["results"]) == Territory.objects.filter(ativo=True).count() >= 17
        assert "next" not in resposta.data

    def test_territorio_inativo_fica_fora(self, auth_client, execucao_rn, territory_rn):
        Territory.objects.filter(pk=territory_rn.pk).update(ativo=False)

        assert territory_rn.pk not in _por_territorio(auth_client.get(RANKING))

    def test_choices_da_curva_e_do_ranking(self, auth_client):
        resposta = auth_client.get("/api/v1/choices/")

        assert [item["value"] for item in resposta.data["curva_escopo"]] == ["projeto", "meta", "submeta", "rubrica"]
        assert [item["value"] for item in resposta.data["ranking_ordenar"]] == ["fisico", "financeiro", "indice"]

    def test_exportacao_em_csv(self, auth_client, execucao_rn, territory_rn):
        resposta = auth_client.get(f"{RANKING}exportar/", {"formato": "csv"})

        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/csv")
        conteudo = resposta.content.decode("utf-8-sig")
        assert "Posição física" in conteudo
        assert territory_rn.nome in conteudo
