from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory
from apps.sgp.models import ActivityDocument, ActivityPhoto, AdherenceIndex, TEDVersion, WorkPlanAcao
from apps.sgp.tasks import calculate_adherence_index
from apps.sgp.ted import execucao
from apps.sgp.ted.services import gerar_snapshot_do_plano
from apps.sgp.tests.factories import (
    ActivityFactory,
    MembroFactory,
    UFPAFactory,
    BudgetRubricaFactory,
    IndicatorFactory,
    TEDVersionFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
    WorkPlanSubmetaFactory,
)

pytestmark = pytest.mark.django_db

Escopo = AdherenceIndex.Escopo
Faixa = AdherenceIndex.Faixa
URL = "/api/v1/sgp/ted/"
ADERENCIA = f"{URL}aderencia/"
HISTORICO = f"{URL}aderencia/historico/"
RECALCULAR = f"{URL}aderencia/recalcular/"
CUSTO = f"{URL}custo-por-entrega/"
COMPOSICAO = f"{URL}custo-por-entrega/composicao/"
RASTREABILIDADE = f"{URL}rastreabilidade/"


@pytest.fixture
def diarias():
    return BudgetRubricaFactory(slug="diarias-monitoramento", nome="Diárias")


@pytest.fixture
def plano(db):
    """Ação 1.1.1: 10 oficinas a R$ 100, no TED."""
    meta = WorkPlanMetaFactory(numero=1, titulo="Meta 1")
    submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1", titulo="Formação")
    acao = WorkPlanAcaoFactory(
        meta=meta, submeta=submeta, numero="1.1.1", indicador=IndicatorFactory(),
        quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
    )
    return acao


@pytest.fixture
def versao(plano):
    return TEDVersionFactory(valor_global=Decimal("1000"), plano_snapshot=gerar_snapshot_do_plano())


def _concluidas(acao, municipio, quantidade):
    return [ActivityFactory(acao=acao, municipio=municipio, status="concluido") for _ in range(quantidade)]


def _paga(atividade, rubrica, valor, *, status="concluida"):
    demanda = DemandFactory(activity=atividade, status=status)
    return DemandRequestFactory(demanda=demanda, rubrica=rubrica, valor_pago=Decimal(valor))


@pytest.fixture
def execucao_rn(plano, versao, municipio_rn, diarias):
    """5 oficinas concluídas no RN e R$ 400 pagos: físico 50 %, financeiro 40 %."""
    atividades = _concluidas(plano, municipio_rn, 5)
    _paga(atividades[0], diarias, "400")
    return atividades


def _linhas(resposta):
    assert resposta.status_code == 200, resposta.data
    return resposta.data["results"]


# ---------------------------------------------------------------------------
# Faixas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fisico, financeiro, indice, faixa", [
    ("50", "40", "1.25", Faixa.SUBEXECUCAO_FINANCEIRA),
    ("48", "40", "1.20", Faixa.EQUILIBRADA),
    ("38", "40", "0.95", Faixa.EQUILIBRADA),
    ("37.6", "40", "0.94", Faixa.ATENCAO),
    ("32", "40", "0.80", Faixa.ATENCAO),
    ("31.6", "40", "0.79", Faixa.CRITICA),
])
def test_faixas_do_indice(fisico, financeiro, indice, faixa):
    assert execucao.faixa_de_aderencia(Decimal(fisico), Decimal(financeiro)) == (Decimal(indice), faixa)


def test_entrega_sem_gasto_e_subexecucao_sem_indice():
    assert execucao.faixa_de_aderencia(Decimal("10"), Decimal("0")) == (None, Faixa.SUBEXECUCAO_FINANCEIRA)


def test_sem_entrega_nem_gasto_nao_tem_faixa():
    assert execucao.faixa_de_aderencia(Decimal("0"), Decimal("0")) == (None, None)


# ---------------------------------------------------------------------------
# Aderência por escopo
# ---------------------------------------------------------------------------

class TestAderencia:
    def test_por_acao(self, auth_client, plano, versao, execucao_rn):
        resposta = auth_client.get(ADERENCIA, {"escopo": "acao"})

        linha = _linhas(resposta)[0]
        assert linha["referencia_id"] == plano.pk
        assert (linha["perc_fisico"], linha["perc_financeiro"], linha["indice"], linha["faixa"]) == (
            "50.00", "40.00", "1.25", Faixa.SUBEXECUCAO_FINANCEIRA,
        )
        assert resposta.data["versao"]["id"] == versao.pk
        assert resposta.data["acoes_fora_da_versao"] == 0

    @pytest.mark.parametrize("escopo", ["submeta", "meta", "indicador", "projeto"])
    def test_niveis_somam_as_acoes(self, auth_client, plano, versao, execucao_rn, escopo):
        WorkPlanAcaoFactory(
            meta=plano.meta, submeta=plano.submeta, numero="1.1.2", indicador=plano.indicador,
            quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
        )
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())

        linhas = _linhas(auth_client.get(ADERENCIA, {"escopo": escopo}))

        assert len(linhas) == 1
        assert (linhas[0]["quantidade_planejada"], linhas[0]["quantidade_realizada"]) == ("20.00", "5.00")
        assert (linhas[0]["perc_fisico"], linhas[0]["perc_financeiro"], linhas[0]["indice"]) == (
            "25.00", "20.00", "1.25",
        )

    def test_por_territorio(self, auth_client, plano, versao, municipio_rn, municipio_ce, diarias,
                            territory_rn, territory_ce):
        rn = _concluidas(plano, municipio_rn, 3)
        _concluidas(plano, municipio_ce, 2)
        _paga(rn[0], diarias, "400")

        linhas = {linha["referencia_id"]: linha for linha in _linhas(auth_client.get(ADERENCIA, {"escopo": "territorio"}))}

        assert (linhas[territory_rn.pk]["perc_fisico"], linhas[territory_rn.pk]["perc_financeiro"]) == ("30.00", "40.00")
        assert (linhas[territory_rn.pk]["indice"], linhas[territory_rn.pk]["faixa"]) == ("0.75", Faixa.CRITICA)
        assert (linhas[territory_ce.pk]["indice"], linhas[territory_ce.pk]["faixa"]) == (
            None, Faixa.SUBEXECUCAO_FINANCEIRA,
        )

    def test_demanda_nao_concluida_nao_entra_no_executado(self, auth_client, plano, versao, municipio_rn, diarias):
        atividade = _concluidas(plano, municipio_rn, 1)[0]
        _paga(atividade, diarias, "400", status="autorizada")

        linha = _linhas(auth_client.get(ADERENCIA, {"escopo": "acao"}))[0]

        assert linha["valor_executado"] == "0.00"

    def test_consultas_nao_crescem_com_as_acoes(self, auth_client, plano, versao, execucao_rn):
        with CaptureQueriesContext(connection) as uma:
            auth_client.get(ADERENCIA, {"escopo": "acao"})
        for numero in range(2, 6):
            WorkPlanAcaoFactory(meta=plano.meta, submeta=plano.submeta, numero=f"1.1.{numero}")
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())

        with CaptureQueriesContext(connection) as cinco:
            resposta = auth_client.get(ADERENCIA, {"escopo": "acao"})

        assert len(_linhas(resposta)) == 5
        assert len(cinco.captured_queries) == len(uma.captured_queries)


# ---------------------------------------------------------------------------
# Relatório contra uma versão
# ---------------------------------------------------------------------------

class TestVersaoDoRelatorio:
    @pytest.fixture
    def aditivo(self, plano, versao, execucao_rn):
        plano.quantidade_planejada = Decimal("20")
        plano.save()
        return TEDVersionFactory(
            ted=versao.ted, numero_versao=2, tipo=TEDVersion.Tipo.ADITIVO,
            valor_global=Decimal("2000"), plano_snapshot=gerar_snapshot_do_plano(),
        )

    def test_vigente_e_o_padrao(self, auth_client, aditivo):
        resposta = auth_client.get(ADERENCIA, {"escopo": "acao"})

        assert resposta.data["versao"]["numero_versao"] == 2
        assert _linhas(resposta)[0]["perc_fisico"] == "25.00"

    def test_versao_anterior(self, auth_client, versao, aditivo):
        resposta = auth_client.get(ADERENCIA, {"escopo": "acao", "versao": versao.pk})

        assert resposta.data["versao"]["numero_versao"] == 1
        assert _linhas(resposta)[0]["perc_fisico"] == "50.00"

    def test_versao_vigente_numa_data(self, auth_client, versao, aditivo):
        ontem = timezone.now() - timedelta(days=1)
        TEDVersion.objects.filter(pk=versao.pk).update(registrado_em=ontem - timedelta(days=30))
        TEDVersion.objects.filter(pk=aditivo.pk).update(registrado_em=timezone.now())

        resposta = auth_client.get(ADERENCIA, {"escopo": "acao", "data": timezone.localdate(ontem).isoformat()})

        assert resposta.data["versao"]["numero_versao"] == 1

    def test_acao_fora_da_versao_fica_de_fora(self, auth_client, plano, versao, execucao_rn):
        nova = WorkPlanAcaoFactory(meta=plano.meta, submeta=plano.submeta, numero="1.1.9")

        resposta = auth_client.get(ADERENCIA, {"escopo": "acao"})

        assert resposta.data["acoes_fora_da_versao"] == 1
        assert nova.pk not in [linha["referencia_id"] for linha in _linhas(resposta)]

    def test_sem_ted_cadastrado(self, auth_client, plano):
        resposta = auth_client.get(ADERENCIA, {"escopo": "acao"})

        assert resposta.status_code == 400
        assert resposta.data["code"] == "ted_nao_cadastrado"

    @pytest.mark.parametrize("parametros", [
        {"escopo": "acao", "versao": 999999},
        {"escopo": "acao", "versao": 1, "data": "2026-01-01"},
        {"escopo": "planeta"},
        {"escopo": "acao", "data": "ontem"},
        {"escopo": "acao", "periodo_inicio": "2026-02-01", "periodo_fim": "2026-01-01"},
    ])
    def test_parametros_invalidos(self, auth_client, versao, parametros):
        assert auth_client.get(ADERENCIA, parametros).status_code == 400


# ---------------------------------------------------------------------------
# Série histórica
# ---------------------------------------------------------------------------

class TestSerieHistorica:
    def test_task_grava_o_mes_corrente_de_todos_os_escopos(self, plano, versao, execucao_rn):
        gravados = calculate_adherence_index()

        mes = execucao.mes_da_serie(timezone.localdate())
        assert gravados == AdherenceIndex.objects.filter(periodo_ref=mes).count()
        assert set(AdherenceIndex.objects.values_list("escopo", flat=True)) == set(Escopo.values)
        acao = AdherenceIndex.objects.get(escopo=Escopo.ACAO, referencia_id=plano.pk)
        assert (acao.indice, acao.faixa, acao.ted_versao_id) == (Decimal("1.25"), Faixa.SUBEXECUCAO_FINANCEIRA, versao.pk)

    def test_rodar_de_novo_atualiza_sem_duplicar(self, plano, versao, execucao_rn, municipio_rn):
        calculate_adherence_index()
        _concluidas(plano, municipio_rn, 3)

        calculate_adherence_index()

        linhas = AdherenceIndex.objects.filter(escopo=Escopo.ACAO, referencia_id=plano.pk)
        assert linhas.count() == 1
        assert linhas.get().perc_fisico == Decimal("80.00")

    def test_mes_anterior_nao_muda(self, plano, versao, execucao_rn):
        anterior = (execucao.mes_da_serie(timezone.localdate()) - timedelta(days=1)).replace(day=1)
        AdherenceIndex.objects.create(
            escopo=Escopo.ACAO, referencia_id=plano.pk, periodo_ref=anterior, ted_versao=versao,
            perc_fisico=Decimal("10"), perc_financeiro=Decimal("10"), indice=Decimal("1.00"), faixa=Faixa.EQUILIBRADA,
        )

        calculate_adherence_index()

        assert AdherenceIndex.objects.get(periodo_ref=anterior, escopo=Escopo.ACAO).perc_fisico == Decimal("10.00")

    def test_sem_ted_nao_grava(self, plano):
        assert calculate_adherence_index() == 0
        assert not AdherenceIndex.objects.exists()

    def test_historico_pelo_endpoint(self, auth_client, plano, versao, execucao_rn):
        calculate_adherence_index()

        resposta = auth_client.get(HISTORICO, {"escopo": "acao", "referencia_id": plano.pk})

        assert resposta.status_code == 200
        assert [linha["indice"] for linha in resposta.data["results"]] == ["1.25"]
        assert resposta.data["results"][0]["ted_versao"]["numero_versao"] == 1

    def test_articulador_le_so_a_serie_dos_seus_territorios(
        self, request, plano, versao, municipio_rn, municipio_ce, diarias, territory_rn,
    ):
        _concluidas(plano, municipio_rn, 1)
        _concluidas(plano, municipio_ce, 1)
        calculate_adherence_index()
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        territorios = cliente.get(HISTORICO, {"escopo": "territorio"})

        assert territorios.status_code == 200
        assert {linha["referencia_id"] for linha in territorios.data["results"]} == {territory_rn.pk}
        assert cliente.get(HISTORICO, {"escopo": "meta"}).status_code == 403

    def test_recalculo_sob_demanda(self, auth_client, django_capture_on_commit_callbacks):
        with patch("apps.sgp.ted.views.calculate_adherence_index.delay") as delay, \
                django_capture_on_commit_callbacks(execute=True):
            resposta = auth_client.post(RECALCULAR)

        assert resposta.status_code == 202
        delay.assert_called_once_with()

    @pytest.mark.parametrize("cliente", ["auth_client_articulador_rn", "auth_client_fgd"])
    def test_recalculo_so_da_ugp_e_do_super_admin(self, request, cliente):
        with patch("apps.sgp.ted.views.calculate_adherence_index.delay") as delay:
            resposta = request.getfixturevalue(cliente).post(RECALCULAR)

        assert resposta.status_code == 403
        delay.assert_not_called()


# ---------------------------------------------------------------------------
# Custo por entrega
# ---------------------------------------------------------------------------

class TestCustoPorEntrega:
    def test_por_acao(self, auth_client, plano, execucao_rn):
        resposta = auth_client.get(CUSTO, {"agrupar": "acao"})

        linha = _linhas(resposta)[0]
        assert (linha["custo_unitario_realizado"], linha["custo_unitario_previsto"]) == ("80.00", "100.00")
        assert (linha["desvio_percentual"], linha["faixa"]) == ("-20.00", execucao.FaixaDeCusto.DENTRO)
        assert resposta.data["limiar_desvio_percentual"] == "20.00"

    def test_limiar_configurado(self, auth_client, plano, execucao_rn, monkeypatch):
        monkeypatch.setattr("apps.sgp.ted.execucao.get_config", lambda chave, padrao=None: 10)

        linha = _linhas(auth_client.get(CUSTO, {"agrupar": "acao"}))[0]

        assert linha["faixa"] == execucao.FaixaDeCusto.ABAIXO

    def test_acima_do_previsto(self, auth_client, plano, versao, municipio_rn, diarias):
        atividade = _concluidas(plano, municipio_rn, 2)[0]
        _paga(atividade, diarias, "300")

        linha = _linhas(auth_client.get(CUSTO, {"agrupar": "acao"}))[0]

        assert (linha["custo_unitario_realizado"], linha["desvio_percentual"], linha["faixa"]) == (
            "150.00", "50.00", execucao.FaixaDeCusto.ACIMA,
        )

    def test_por_indicador_consolida_as_acoes(self, auth_client, plano, versao, municipio_rn, diarias):
        outra = WorkPlanAcaoFactory(
            meta=plano.meta, submeta=plano.submeta, numero="1.1.2", indicador=plano.indicador,
            quantidade_planejada=Decimal("10"), valor_unitario=Decimal("300"),
        )
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())
        _paga(_concluidas(plano, municipio_rn, 1)[0], diarias, "100")
        _paga(_concluidas(outra, municipio_rn, 1)[0], diarias, "300")

        linha = _linhas(auth_client.get(CUSTO, {"agrupar": "indicador"}))[0]

        assert linha["referencia_id"] == plano.indicador_id
        assert (linha["custo_unitario_previsto"], linha["custo_unitario_realizado"]) == ("200.00", "200.00")

    def test_por_territorio_compara_o_mesmo_indicador(
        self, auth_client, plano, versao, municipio_rn, municipio_ce, diarias, territory_rn, territory_ce,
    ):
        _paga(_concluidas(plano, municipio_rn, 1)[0], diarias, "100")
        _paga(_concluidas(plano, municipio_ce, 1)[0], diarias, "160")

        linhas = {linha["territorio_id"]: linha for linha in _linhas(auth_client.get(CUSTO, {"agrupar": "territorio"}))}

        assert linhas[territory_rn.pk]["custo_unitario_realizado"] == "100.00"
        assert (linhas[territory_ce.pk]["custo_unitario_realizado"], linhas[territory_ce.pk]["faixa"]) == (
            "160.00", execucao.FaixaDeCusto.ACIMA,
        )
        assert list(linhas) == [territory_ce.pk, territory_rn.pk]

    def test_composicao_por_rubrica(self, auth_client, plano, versao, municipio_rn, diarias):
        material = BudgetRubricaFactory(slug="material-monitoramento", nome="Material")
        atividade = _concluidas(plano, municipio_rn, 1)[0]
        _paga(atividade, diarias, "300")
        _paga(atividade, material, "100")

        resposta = auth_client.get(COMPOSICAO, {"acao_id": plano.pk})

        assert resposta.status_code == 200
        assert resposta.data["count"] == 2
        assert [(item["rubrica"]["slug"], item["participacao_percentual"]) for item in resposta.data["results"]] == [
            ("diarias-monitoramento", "75.00"), ("material-monitoramento", "25.00"),
        ]

    def test_composicao_exige_acao_ou_indicador(self, auth_client, plano):
        assert auth_client.get(COMPOSICAO).status_code == 400
        assert auth_client.get(COMPOSICAO, {"acao_id": plano.pk, "indicador_id": plano.indicador_id}).status_code == 400


# ---------------------------------------------------------------------------
# Rastreabilidade
# ---------------------------------------------------------------------------

class TestRastreabilidade:
    def test_da_rubrica_a_evidencia(self, auth_client, plano, versao, municipio_rn, diarias, territory_rn):
        atividade = _concluidas(plano, municipio_rn, 1)[0]
        solicitacao = _paga(atividade, diarias, "400")

        resposta = auth_client.get(RASTREABILIDADE, {"rubrica": diarias.slug})

        assert resposta.status_code == 200, resposta.data
        item = resposta.data["results"][0]
        assert item["solicitacao_id"] == solicitacao.pk
        assert item["valor_pago"] == "400.00"
        assert item["demanda"]["id"] == solicitacao.demanda_id
        assert (item["atividade"]["id"], item["atividade"]["territorio"]) == (atividade.pk, territory_rn.nome)
        assert item["plano_trabalho"]["acao"]["numero"] == "1.1.1"
        assert item["plano_trabalho"]["indicador"]["codigo"] == plano.indicador.codigo
        assert item["evidencias"] == {"fotos": 0, "documentos": 0, "listas_presenca": 0, "ufpas": 0, "membros": 0}

    def test_filtros_por_rubrica_territorio_e_status(
        self, auth_client, plano, versao, municipio_rn, municipio_ce, diarias, territory_rn,
    ):
        material = BudgetRubricaFactory(slug="material-rastreio")
        rn = _concluidas(plano, municipio_rn, 1)[0]
        ce = _concluidas(plano, municipio_ce, 1)[0]
        no_rn = _paga(rn, diarias, "100")
        _paga(ce, diarias, "100")
        _paga(rn, material, "100")
        _paga(rn, diarias, "100", status="autorizada")

        resposta = auth_client.get(RASTREABILIDADE, {"rubrica": diarias.slug, "territorio_id": territory_rn.pk})

        assert [item["solicitacao_id"] for item in resposta.data["results"]] == [no_rn.pk]

    def test_rubrica_inexistente(self, auth_client, plano):
        assert auth_client.get(RASTREABILIDADE, {"rubrica": "nao-existe"}).status_code == 400


# ---------------------------------------------------------------------------
# Perfis
# ---------------------------------------------------------------------------

ROTAS_DE_LEITURA = [
    (ADERENCIA, {"escopo": "acao"}),
    (CUSTO, {"agrupar": "acao"}),
    (RASTREABILIDADE, {"rubrica": "diarias-monitoramento"}),
]


class TestPerfis:
    @pytest.mark.parametrize("cliente", ["auth_client", "auth_client_super_admin", "auth_client_fgd"])
    def test_leitura_global(self, request, execucao_rn, cliente):
        cliente = request.getfixturevalue(cliente)

        assert [cliente.get(rota, params).status_code for rota, params in ROTAS_DE_LEITURA] == [200] * 3

    def test_articulador_ve_so_os_seus_estados(self, request, plano, versao, municipio_rn, municipio_ce, diarias):
        _concluidas(plano, municipio_rn, 2)
        _paga(_concluidas(plano, municipio_ce, 3)[0], diarias, "500")
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        linha = _linhas(cliente.get(ADERENCIA, {"escopo": "acao"}))[0]

        assert (linha["quantidade_realizada"], linha["valor_executado"]) == ("2.00", "0.00")
        assert cliente.get(RASTREABILIDADE, {"rubrica": diarias.slug}).data["count"] == 0

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_sem_acesso"])
    def test_adt_e_agricultor_nao_acessam(self, request, versao, cliente):
        cliente = request.getfixturevalue(cliente)

        assert [cliente.get(rota, params).status_code for rota, params in ROTAS_DE_LEITURA] == [403] * 3

    def test_anonimo_recebe_401(self, api_client, versao):
        assert [api_client.get(rota, params).status_code for rota, params in ROTAS_DE_LEITURA] == [401] * 3


# ---------------------------------------------------------------------------
# Recortes, bordas e relatórios novos
# ---------------------------------------------------------------------------

@pytest.fixture
def acao_manual(plano, versao, municipio_rn, diarias):
    """Ação 1.1.2 com Indicador de lançamento manual: 5 de 10 lançados pela UGP e
    R$ 500 pagos numa atividade do RN."""
    manual = WorkPlanAcaoFactory(
        meta=plano.meta, submeta=plano.submeta, numero="1.1.2",
        indicador=IndicatorFactory(forma_apuracao="manual"),
        quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
    )
    WorkPlanAcao.objects.filter(pk=manual.pk).update(quantidade_realizada=5)
    TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())
    _paga(ActivityFactory(acao=manual, municipio=municipio_rn, status="concluido"), diarias, "500")
    return manual


class TestLancamentoManual:
    def test_sem_recorte_entra_com_o_lancado(self, auth_client, plano, acao_manual):
        linhas = {linha["referencia_id"]: linha for linha in _linhas(auth_client.get(ADERENCIA, {"escopo": "acao"}))}

        assert linhas[acao_manual.pk]["quantidade_realizada"] == "5.00"

    def test_quebra_por_territorio_deixa_a_manual_de_fora(self, auth_client, plano, acao_manual, territory_rn):
        resposta = auth_client.get(ADERENCIA, {"escopo": "territorio"})

        assert resposta.data["acoes_manuais_fora_do_recorte"] == 1
        assert _linhas(resposta) == []

    def test_recorte_por_territorio_deixa_a_manual_de_fora(self, auth_client, plano, acao_manual, territory_rn):
        resposta = auth_client.get(ADERENCIA, {"escopo": "acao", "territorio_id": territory_rn.pk})

        assert resposta.data["acoes_manuais_fora_do_recorte"] == 1
        assert acao_manual.pk not in [linha["referencia_id"] for linha in _linhas(resposta)]


class TestEdgeCases:
    def test_acao_da_versao_apagada_entra_com_o_planejado(self, auth_client, plano, versao, execucao_rn):
        sem_execucao = WorkPlanAcaoFactory(
            meta=plano.meta, submeta=plano.submeta, numero="1.1.3",
            quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
        )
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())
        sem_execucao.delete()

        resposta = auth_client.get(ADERENCIA, {"escopo": "projeto"})

        assert resposta.data["acoes_da_versao_fora_do_plano"] == 1
        assert _linhas(resposta)[0]["valor_planejado"] == "2000.00"

    def test_razao_extrema_nao_derruba_a_serie(self, plano, versao, municipio_rn, diarias):
        WorkPlanAcao.objects.filter(pk=plano.pk).update(valor_unitario=Decimal("0.01"))
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())
        _paga(_concluidas(plano, municipio_rn, 1)[0], diarias, "999999999.00")

        assert calculate_adherence_index() > 0
        linha = AdherenceIndex.objects.get(escopo=Escopo.ACAO, referencia_id=plano.pk)
        assert linha.perc_financeiro > Decimal("1000000")

    @pytest.mark.parametrize("valor, limiar", [("15,5", "15.50"), ("abc", "20.00"), (-5, "20.00"), (None, "20.00")])
    def test_limiar_do_custo_ilegivel_vale_o_padrao(self, auth_client, plano, execucao_rn, monkeypatch, valor, limiar):
        monkeypatch.setattr(
            "apps.sgp.ted.execucao.get_config", lambda chave, padrao=None: padrao if valor is None else valor,
        )

        resposta = auth_client.get(CUSTO, {"agrupar": "acao"})

        assert resposta.status_code == 200
        assert resposta.data["limiar_desvio_percentual"] == limiar

    def test_ranking_pelo_tamanho_do_desvio(self, auth_client, plano, versao, municipio_rn, diarias):
        barata = WorkPlanAcaoFactory(
            meta=plano.meta, submeta=plano.submeta, numero="1.1.2", indicador=plano.indicador,
            quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
        )
        TEDVersion.objects.filter(pk=versao.pk).update(plano_snapshot=gerar_snapshot_do_plano())
        _paga(_concluidas(plano, municipio_rn, 1)[0], diarias, "101")
        _paga(_concluidas(barata, municipio_rn, 1)[0], diarias, "20")

        linhas = _linhas(auth_client.get(CUSTO, {"agrupar": "acao"}))

        assert [linha["desvio_percentual"] for linha in linhas] == ["-80.00", "1.00"]


class TestEscopoDoArticulador:
    def test_perfil_de_adt_nao_amplia_o_recorte(
        self, plano, versao, municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        usuario = UserFactory(profiles=[
            (RoleFactory(slug="articulador-estadual", nome="Articulador Estadual"), territory_rn),
            (RoleFactory(slug="adt-acr", nome="ADT"), territory_ce),
        ])
        _concluidas(plano, municipio_rn, 2)
        _concluidas(plano, municipio_ce, 3)

        dados = execucao.execucao(usuario, versao)

        assert dados.realizado[plano.numero] == Decimal("2")

    def test_historico_do_perfil_combinado(self, plano, versao, municipio_rn, municipio_ce, territory_rn, territory_ce):
        _concluidas(plano, municipio_rn, 1)
        _concluidas(plano, municipio_ce, 1)
        calculate_adherence_index()
        usuario = UserFactory(profiles=[
            (RoleFactory(slug="articulador-estadual", nome="Articulador Estadual"), territory_rn),
            (RoleFactory(slug="adt-acr", nome="ADT"), territory_ce),
        ])
        cliente = APIClient()
        cliente.force_authenticate(user=usuario)

        resposta = cliente.get(HISTORICO, {"escopo": "territorio"})

        assert resposta.status_code == 200
        assert {linha["referencia_id"] for linha in resposta.data["results"]} == {territory_rn.pk}

    def test_territorio_que_cruza_estados_fica_fora_do_historico(self, request, plano, versao, state_rn):
        from apps.core.tests.factories import MunicipalityFactory

        dividido = TerritoryFactory(nome="RN e PB", estados=["RN", "PB"])
        _concluidas(plano, MunicipalityFactory(state=state_rn, territory=dividido), 1)
        calculate_adherence_index()
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        resposta = cliente.get(HISTORICO, {"escopo": "territorio"})

        assert dividido.pk not in {linha["referencia_id"] for linha in resposta.data["results"]}

    def test_rastreabilidade_segue_o_estado_da_atividade(self, request, plano, versao, municipio_rn, diarias):
        atividade = _concluidas(plano, municipio_rn, 1)[0]
        demanda = DemandFactory(activity=atividade, status="concluida", estado_sigla="PB", territorio=None)
        DemandRequestFactory(demanda=demanda, rubrica=diarias, valor_pago=Decimal("100"))
        cliente = request.getfixturevalue("auth_client_articulador_rn")

        resposta = cliente.get(RASTREABILIDADE, {"rubrica": diarias.slug})

        assert resposta.data["count"] == 1


class TestEvidencias:
    def test_contagens_de_cada_evidencia(self, auth_client, plano, versao, municipio_rn, diarias):
        atividade = _concluidas(plano, municipio_rn, 1)[0]
        for ordem in range(2):
            ActivityPhoto.objects.create(
                activity=atividade, arquivo_key=f"atividades/{atividade.pk}/fotos/{ordem}.jpg",
                arquivo_url="https://cdn.example.com/foto.jpg", ordem=ordem, ativo=True,
            )
        for tipo in (ActivityDocument.TIPO_LISTA_PRESENCA, ActivityDocument.TIPO_ATA):
            ActivityDocument.objects.create(
                activity=atividade, arquivo_key=f"atividades/{atividade.pk}/documentos/{tipo}.pdf",
                arquivo_url="https://cdn.example.com/doc.pdf", tipo=tipo, nome_original="doc.pdf",
                data_documento=date(2026, 8, 1), ativo=True,
            )
        ufpas = [UFPAFactory(municipio=municipio_rn) for _ in range(3)]
        atividade.ufpas_participantes.set(ufpas)
        atividade.membros_participantes.set([MembroFactory(ufpa=ufpas[0]) for _ in range(2)])
        _paga(atividade, diarias, "100")

        item = auth_client.get(RASTREABILIDADE, {"rubrica": diarias.slug}).data["results"][0]

        assert item["evidencias"] == {"fotos": 2, "documentos": 2, "listas_presenca": 1, "ufpas": 3, "membros": 2}


class TestExportacao:
    def test_aderencia_em_csv(self, auth_client, plano, execucao_rn):
        resposta = auth_client.get(f"{ADERENCIA}exportar/", {"escopo": "acao", "formato": "csv"})

        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/csv")
        linhas = resposta.content.decode("utf-8-sig").splitlines()
        assert linhas[0].startswith("Referência,Nome")
        assert "1.25" in linhas[1]

    def test_custo_em_xlsx(self, auth_client, plano, execucao_rn):
        resposta = auth_client.get(f"{CUSTO}exportar/", {"agrupar": "acao", "formato": "xlsx"})

        assert resposta.status_code == 200
        assert "spreadsheetml" in resposta["Content-Type"]


class TestComparativoDeVersoes:
    def test_mostra_so_o_que_mudou(self, auth_client, plano, versao):
        plano.quantidade_planejada = Decimal("20")
        plano.save()
        WorkPlanAcaoFactory(meta=plano.meta, submeta=plano.submeta, numero="1.1.2")
        aditivo = TEDVersionFactory(
            ted=versao.ted, numero_versao=2, tipo=TEDVersion.Tipo.ADITIVO, plano_snapshot=gerar_snapshot_do_plano(),
        )

        resposta = auth_client.get(
            f"{URL}{versao.ted_id}/versoes/comparar/", {"de": versao.pk, "para": aditivo.pk},
        )

        assert resposta.status_code == 200, resposta.data
        por_chave = {(d["elemento"], d["chave"]): d for d in resposta.data["diferencas"]}
        assert por_chave[("acao", "1.1.1")]["situacao"] == "alterada"
        assert "quantidade_planejada" in por_chave[("acao", "1.1.1")]["campos_alterados"]
        assert por_chave[("acao", "1.1.2")]["situacao"] == "incluida"
        assert ("meta", "1") in por_chave

    def test_versao_de_outro_ted(self, auth_client, versao):
        resposta = auth_client.get(f"{URL}{versao.ted_id}/versoes/comparar/", {"de": versao.pk, "para": 999999})

        assert resposta.status_code == 400
