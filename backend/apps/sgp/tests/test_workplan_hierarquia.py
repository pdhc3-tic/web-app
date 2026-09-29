"""Hierarquia Meta → Submeta → Ação → Indicador nos consumidores do PT:
valor executado (SGP §5.5), painel em árvore (RF23), visão por Indicador
(RF22), exportação e Power BI (RF25/RF26) e Atividades (RF07/RF15)."""
import csv
import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status

from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.models import WorkPlanAcao
from apps.sgp.services.apuracao import recalcular_valor_executado
from apps.sgp.services.visao_indicador import Granularidade
from apps.sgp.services.workplan_export import EXPORT_COLUMNS, workplan_export_rows
from apps.sgp.tests.factories import (
    ActivityFactory,
    IndicatorFactory,
    UPFFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
    WorkPlanSubmetaFactory,
)

pytestmark = pytest.mark.django_db

PAINEL_URL = "/api/v1/sgp/plano-trabalho/painel/"
VISAO_URL = "/api/v1/sgp/plano-trabalho/indicadores/"
EXPORT_URL = "/api/v1/sgp/plano-trabalho/exportar/"
ATIVIDADES_URL = "/api/v1/sgp/atividades/"


def _concluir_demanda(atividade, valor_pago, status_demanda="concluida"):
    demanda = DemandFactory(activity=atividade, status=status_demanda)
    DemandRequestFactory(demanda=demanda, valor_estimado=valor_pago, valor_pago=valor_pago)
    # Na API isso acontece no `concluir` do SGD; aqui a demanda nasce concluída.
    recalcular_valor_executado([atividade.acao_id])
    return demanda


@pytest.fixture
def meta():
    return WorkPlanMetaFactory(
        numero=1, data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31)
    )


@pytest.fixture
def arvore(meta, municipio_rn):
    """Submeta 1.1 com duas Ações e Submeta 1.2 com uma, todas no mesmo Indicador."""
    indicador = IndicatorFactory(codigo="TST-OFI", nome="Oficinas")
    s1 = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
    s2 = WorkPlanSubmetaFactory(meta=meta, numero="1.2")
    a1 = WorkPlanAcaoFactory(
        meta=meta, submeta=s1, numero="1.1.1", indicador=indicador,
        quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
    )
    a2 = WorkPlanAcaoFactory(
        meta=meta, submeta=s1, numero="1.1.2", indicador=indicador,
        quantidade_planejada=Decimal("10"), valor_unitario=Decimal("100"),
    )
    b1 = WorkPlanAcaoFactory(
        meta=meta, submeta=s2, numero="1.2.1", indicador=indicador,
        quantidade_planejada=Decimal("5"), valor_unitario=Decimal("100"),
    )
    atividades = [
        ActivityFactory(acao=a1, status="concluido", municipio=municipio_rn) for _ in range(4)
    ]
    ActivityFactory(acao=b1, status="concluido", municipio=municipio_rn)
    return {"indicador": indicador, "s1": s1, "s2": s2, "a1": a1, "a2": a2, "b1": b1,
            "atividades": atividades}


class TestValorExecutado:
    def test_soma_so_demandas_concluidas(self, arvore):
        atividade = arvore["atividades"][0]
        _concluir_demanda(atividade, Decimal("500.00"))
        _concluir_demanda(atividade, Decimal("300.00"))
        _concluir_demanda(atividade, Decimal("999.00"), status_demanda="em_atendimento")

        a1 = WorkPlanAcao.objects.get(pk=arvore["a1"].pk)
        assert a1.valor_executado == Decimal("800.00")
        assert a1.custo_unitario_realizado == Decimal("200.00")

    def test_atividade_que_muda_de_acao_leva_o_valor(self, arvore):
        atividade = arvore["atividades"][0]
        _concluir_demanda(atividade, Decimal("500.00"))

        atividade.acao = arvore["a2"]
        atividade.save()

        assert WorkPlanAcao.objects.get(pk=arvore["a1"].pk).valor_executado == 0
        assert WorkPlanAcao.objects.get(pk=arvore["a2"].pk).valor_executado == Decimal("500.00")

    def test_atividade_desativada_sai_do_valor(self, arvore):
        atividade = arvore["atividades"][0]
        _concluir_demanda(atividade, Decimal("500.00"))

        atividade.soft_delete()

        assert WorkPlanAcao.objects.get(pk=arvore["a1"].pk).valor_executado == 0

    def test_reconciliacao_corrige_valor(self, arvore):
        atividade = arvore["atividades"][0]
        _concluir_demanda(atividade, Decimal("500.00"))
        WorkPlanAcao.objects.filter(pk=arvore["a1"].pk).update(valor_executado=Decimal("1"))

        call_command("verificar_progresso_acoes")

        assert WorkPlanAcao.objects.get(pk=arvore["a1"].pk).valor_executado == Decimal("500.00")

    def test_consolidados_da_submeta_e_da_meta(self, arvore, meta):
        _concluir_demanda(arvore["atividades"][0], Decimal("800.00"))

        s1 = arvore["s1"]
        assert s1.quantidade_planejada == Decimal("20")
        assert s1.quantidade_realizada == 4
        assert s1.valor_total == Decimal("2000")
        assert s1.valor_executado == Decimal("800.00")
        assert meta.quantidade_planejada == Decimal("25")
        assert meta.valor_executado == Decimal("800.00")


class TestPainelEmArvore:
    def test_submetas_como_nos_com_consolidados_e_semaforos(self, auth_client, arvore):
        _concluir_demanda(arvore["atividades"][0], Decimal("800.00"))

        response = auth_client.get(PAINEL_URL)

        assert response.status_code == status.HTTP_200_OK
        grupo = response.data["metas"][0]
        assert grupo["resumo"]["total_acoes"] == 3
        assert [no["submeta"]["numero"] for no in grupo["submetas"]] == ["1.1", "1.2"]

        s1 = grupo["submetas"][0]
        assert s1["acoes"] == [arvore["a1"].pk, arvore["a2"].pk]
        assert s1["consolidado"]["quantidade_planejada"] == "20.00"
        assert s1["consolidado"]["quantidade_realizada"] == "4.00"
        assert s1["consolidado"]["valor_executado"] == "800.00"
        assert s1["consolidado"]["percentual_financeiro"] == "40.00"
        assert s1["consolidado"]["semaforo_financeiro"] == "verde"

        a1 = next(a for a in grupo["acoes"] if a["id"] == arvore["a1"].pk)
        assert (a1["submeta"], a1["submeta_numero"], a1["submeta_titulo"]) == (
            arvore["s1"].pk, "1.1", arvore["s1"].titulo
        )
        assert a1["indicador"]["codigo"] == "TST-OFI"
        assert a1["percentual_financeiro"] == "80.00"
        assert a1["semaforo_financeiro"] == "amarelo"
        assert grupo["consolidado"]["valor_total"] == "2500.00"

    def test_adt_ve_quantidade_do_proprio_territorio(self, auth_client_adt_rn, arvore, municipio_ce):
        ActivityFactory(acao=arvore["a1"], status="concluido", municipio=municipio_ce)

        response = auth_client_adt_rn.get(PAINEL_URL)

        acoes = {a["id"]: a for a in response.data["metas"][0]["acoes"]}
        assert acoes[arvore["a1"].pk]["quantidade_realizada"] == "4.00"


class TestVisaoPorIndicador:
    def test_consolida_acoes_de_metas_diferentes(self, auth_client, arvore, municipio_ce):
        outra_meta = WorkPlanMetaFactory(numero=2)
        c1 = WorkPlanAcaoFactory(
            meta=outra_meta, indicador=arvore["indicador"], quantidade_planejada=Decimal("15"),
        )
        ActivityFactory(acao=c1, status="concluido", municipio=municipio_ce)

        response = auth_client.get(VISAO_URL, {"indicador_id": arvore["indicador"].pk})

        assert response.status_code == status.HTTP_200_OK
        [item] = response.data["indicadores"]
        assert item["indicador"]["codigo"] == "TST-OFI"
        assert item["quantidade_planejada"] == "40.00"
        assert item["quantidade_realizada"] == "6.00"
        assert item["percentual_realizado"] == "15.00"
        assert {m["numero"]: m["quantidade_realizada"] for m in item["por_meta"]} == {
            "1": "5.00", "2": "1.00",
        }
        assert {s["numero"] for s in item["por_submeta"]} >= {"1.1", "1.2"}
        assert {t["nome"]: t["quantidade_realizada"] for t in item["por_territorio"]} == {
            "Território RN": 5, "Território CE": 1,
        }

    def test_filtro_de_territorio_e_periodo(self, auth_client, arvore, territory_rn):
        fora_do_periodo = arvore["atividades"][0]
        fora_do_periodo.data_inicio = fora_do_periodo.data_inicio.replace(year=2025)
        fora_do_periodo.data_fim = fora_do_periodo.data_fim.replace(year=2025)
        fora_do_periodo.save()

        response = auth_client.get(VISAO_URL, {
            "territorio_id": territory_rn.pk,
            "periodo_inicio": "2026-01-01",
            "periodo_fim": "2026-12-31",
        })

        [item] = response.data["indicadores"]
        assert item["quantidade_realizada"] == "4.00"

    def test_indicador_manual_nao_tem_realizado_sob_recorte(
        self, auth_client, meta, territory_rn
    ):
        manual = IndicatorFactory(forma_apuracao="manual")
        WorkPlanAcaoFactory(meta=meta, indicador=manual, quantidade_realizada=7)

        sem_recorte = auth_client.get(VISAO_URL, {"indicador_id": manual.pk})
        com_recorte = auth_client.get(
            VISAO_URL, {"indicador_id": manual.pk, "territorio_id": territory_rn.pk}
        )

        assert sem_recorte.data["indicadores"][0]["quantidade_realizada"] == "7.00"
        [item] = com_recorte.data["indicadores"]
        assert item["quantidade_realizada"] is None
        assert item["percentual_realizado"] is None
        assert item["por_meta"][0]["quantidade_realizada"] is None

    def test_periodo_invertido_retorna_400(self, auth_client):
        response = auth_client.get(
            VISAO_URL, {"periodo_inicio": "2026-12-01", "periodo_fim": "2026-01-01"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_adt_so_ve_o_proprio_territorio(self, auth_client_adt_rn, arvore, municipio_ce):
        oculta = WorkPlanAcaoFactory(indicador=arvore["indicador"])
        ActivityFactory(acao=oculta, status="concluido", municipio=municipio_ce)

        response = auth_client_adt_rn.get(VISAO_URL)

        [item] = response.data["indicadores"]
        assert item["quantidade_realizada"] == "5.00"
        assert [t["nome"] for t in item["por_territorio"]] == ["Território RN"]

    def test_ufpas_distintas_por_territorio(self, auth_client, meta, municipio_rn):
        indicador = IndicatorFactory(forma_apuracao="soma_ufpas")
        acao = WorkPlanAcaoFactory(meta=meta, indicador=indicador)
        upf = UPFFactory(municipio=municipio_rn)
        for _ in range(2):
            ActivityFactory(acao=acao, status="concluido", municipio=municipio_rn).upfs_participantes.add(upf)

        response = auth_client.get(VISAO_URL, {"indicador_id": indicador.pk})

        [item] = response.data["indicadores"]
        assert item["quantidade_realizada"] == "1.00"
        assert item["por_territorio"][0]["quantidade_realizada"] == 1


def _no_mes(atividade, mes):
    atividade.data_inicio = timezone.make_aware(datetime(2026, mes, 1, 8))
    atividade.data_fim = timezone.make_aware(datetime(2026, mes, 1, 12))
    atividade.save()
    return atividade


class TestVisaoPorPeriodo:
    def test_quebra_mensal_por_padrao(self, auth_client, arvore):
        _no_mes(arvore["atividades"][0], 2)

        response = auth_client.get(VISAO_URL)

        assert response.data["granularidade"] == "mes"
        [item] = response.data["indicadores"]
        assert item["por_periodo"] == [
            {"inicio": "2026-02-01", "fim": "2026-02-28", "quantidade_realizada": 1},
            {"inicio": "2026-03-01", "fim": "2026-03-31", "quantidade_realizada": 0},
            {"inicio": "2026-04-01", "fim": "2026-04-30", "quantidade_realizada": 0},
            {"inicio": "2026-05-01", "fim": "2026-05-31", "quantidade_realizada": 0},
            {"inicio": "2026-06-01", "fim": "2026-06-30", "quantidade_realizada": 4},
        ]

    def test_periodo_pedido_recorta_as_pontas_e_completa_com_zero(self, auth_client, arvore):
        response = auth_client.get(VISAO_URL, {
            "granularidade": "trimestre", "periodo_inicio": "2026-05-10", "periodo_fim": "2026-08-20",
        })

        [item] = response.data["indicadores"]
        assert item["por_periodo"] == [
            {"inicio": "2026-05-10", "fim": "2026-06-30", "quantidade_realizada": 5},
            {"inicio": "2026-07-01", "fim": "2026-08-20", "quantidade_realizada": 0},
        ]

    def test_indicador_manual_nao_tem_quebra_por_periodo(self, auth_client, meta):
        manual = IndicatorFactory(forma_apuracao="manual")
        WorkPlanAcaoFactory(meta=meta, indicador=manual, quantidade_realizada=7)

        response = auth_client.get(VISAO_URL, {"indicador_id": manual.pk})

        assert response.data["indicadores"][0]["por_periodo"] == []

    @pytest.mark.parametrize("granularidade,inicio,fim", [
        ("trimestre", "2026-04-01", "2026-06-30"),
        ("semestre", "2026-01-01", "2026-06-30"),
        ("ano", "2026-01-01", "2026-12-31"),
    ])
    def test_outras_granularidades(self, auth_client, arvore, granularidade, inicio, fim):
        response = auth_client.get(VISAO_URL, {"granularidade": granularidade})

        assert response.data["granularidade"] == granularidade
        [item] = response.data["indicadores"]
        assert item["por_periodo"] == [{"inicio": inicio, "fim": fim, "quantidade_realizada": 5}]

    def test_granularidade_desconhecida_retorna_400(self, auth_client):
        response = auth_client.get(VISAO_URL, {"granularidade": "quinzena"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "granularidade" in response.data

    def test_ufpa_distinta_dentro_de_cada_periodo(self, auth_client, meta, municipio_rn):
        indicador = IndicatorFactory(forma_apuracao="soma_ufpas")
        acao = WorkPlanAcaoFactory(meta=meta, indicador=indicador)
        upf = UPFFactory(municipio=municipio_rn)
        for mes in (3, 3, 5):
            atividade = ActivityFactory(acao=acao, status="concluido", municipio=municipio_rn)
            _no_mes(atividade, mes).upfs_participantes.add(upf)

        response = auth_client.get(VISAO_URL, {"indicador_id": indicador.pk})

        [item] = response.data["indicadores"]
        # Distinta dentro de cada fatia: a mesma UFPA conta em março e em maio,
        # mas uma vez só no total.
        assert item["quantidade_realizada"] == "1.00"
        assert [(p["inicio"], p["quantidade_realizada"]) for p in item["por_periodo"]] == [
            ("2026-03-01", 1), ("2026-04-01", 0), ("2026-05-01", 1),
        ]

    def test_so_o_inicio_vai_ate_o_ultimo_realizado(self, auth_client, arvore):
        response = auth_client.get(VISAO_URL, {"periodo_inicio": "2026-04-15"})

        [item] = response.data["indicadores"]
        assert item["por_periodo"] == [
            {"inicio": "2026-04-15", "fim": "2026-04-30", "quantidade_realizada": 0},
            {"inicio": "2026-05-01", "fim": "2026-05-31", "quantidade_realizada": 0},
            {"inicio": "2026-06-01", "fim": "2026-06-30", "quantidade_realizada": 5},
        ]

    def test_um_extremo_sem_realizado_traz_a_fatia_pedida(self, auth_client, meta):
        indicador = IndicatorFactory()
        WorkPlanAcaoFactory(meta=meta, indicador=indicador)

        response = auth_client.get(
            VISAO_URL, {"indicador_id": indicador.pk, "periodo_fim": "2026-03-20"}
        )

        assert response.data["indicadores"][0]["por_periodo"] == [
            {"inicio": "2026-03-01", "fim": "2026-03-20", "quantidade_realizada": 0},
        ]

    def test_periodo_longo_demais_retorna_400(self, auth_client, arvore):
        response = auth_client.get(
            VISAO_URL, {"periodo_inicio": "2000-01-01", "periodo_fim": "2026-12-31"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "periodo_longo_demais"

    def test_granularidade_precisa_dividir_o_ano(self):
        with pytest.raises(ValueError):
            Granularidade(meses=5)


class TestExportacao:
    def test_colunas_da_hierarquia_e_saldo(self, auth_client, arvore):
        _concluir_demanda(arvore["atividades"][0], Decimal("800.00"))

        response = auth_client.get(EXPORT_URL, {"formato": "csv"})

        linhas = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        assert linhas[0] == [label for _, label in EXPORT_COLUMNS]
        assert "Tipo/Unidade" not in linhas[0]
        registro = next(
            r for r in (dict(zip(linhas[0], linha)) for linha in linhas[1:])
            if r["Ação"].startswith("1.1.1")
        )
        assert registro["Número da Submeta"] == "1.1"
        assert registro["Indicador"] == "TST-OFI - Oficinas"
        assert registro["Unidade de medida"] == "Evento"
        assert registro["Valor executado"] == "800.00"
        assert registro["Custo unitário realizado"] == "200.00"
        assert registro["Saldo"] == "200.00"

    def test_arvore_completa_com_consolidado_por_no(self, auth_client, arvore, meta):
        _concluir_demanda(arvore["atividades"][0], Decimal("800.00"))
        WorkPlanSubmetaFactory(meta=meta, numero="1.3")

        response = auth_client.get(EXPORT_URL, {"formato": "csv"})

        linhas = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        registros = [dict(zip(linhas[0], linha)) for linha in linhas[1:]]
        assert [(r["Nível"], r["Número da Submeta"], r["Ação"][:5]) for r in registros] == [
            ("Meta", "", ""),
            ("Submeta", "1.1", ""), ("Ação", "1.1", "1.1.1"), ("Ação", "1.1", "1.1.2"),
            ("Submeta", "1.2", ""), ("Ação", "1.2", "1.2.1"),
            ("Submeta", "1.3", ""),
        ]
        meta_linha, s1_linha, vazia = registros[0], registros[1], registros[-1]
        assert (meta_linha["Valor total"], meta_linha["Valor executado"], meta_linha["Saldo"]) == (
            "2500.00", "800.00", "1700.00"
        )
        assert (s1_linha["Quantidade planejada"], s1_linha["Quantidade realizada"]) == ("20.00", "4")
        assert (vazia["Valor total"], vazia["Quantidade realizada"]) == ("0.00", "0")
        # Sem planejado não há percentual para o semáforo.
        assert vazia["Semáforo"] == ""

    def test_status_da_meta_vem_das_submetas(self, auth_client, meta):
        acao = WorkPlanAcaoFactory(meta=meta, quantidade_planejada=1)
        ActivityFactory(acao=acao, status="concluido")
        WorkPlanSubmetaFactory(meta=meta, numero="1.9")

        response = auth_client.get(EXPORT_URL, {"formato": "csv"})

        linhas = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        registros = [dict(zip(linhas[0], linha)) for linha in linhas[1:]]
        por_nivel = {r["Nível"]: r for r in registros if r["Número da Submeta"] != "1.9"}
        assert por_nivel["Ação"]["Status de execução"] == "concluida"
        # A Submeta 1.9 ainda não tem Ações, então a Meta não está concluída.
        assert por_nivel["Meta"]["Status de execução"] != "concluida"

    def test_total_por_meta_nao_muda(self, arvore):
        linhas = workplan_export_rows()
        total = sum(Decimal(linha["valor_total"]) for linha in linhas if linha["meta"].startswith("1 - "))

        assert total == Decimal("2500.00")

    def test_power_bi_tem_uma_linha_por_acao_com_a_submeta(self, arvore):
        linhas = workplan_export_rows()

        assert {linha["nivel"] for linha in linhas} == {"Ação"}
        a1 = next(linha for linha in linhas if linha["acao"].startswith("1.1.1 "))
        assert (a1["submeta_numero"], a1["submeta_titulo"]) == ("1.1", arvore["s1"].titulo)

    def test_power_bi_mantem_alias_tipo_unidade(self, arvore):
        linha = workplan_export_rows()[0]

        assert linha["tipo_unidade"] == "Oficinas"


class TestLeituraPorPerfil:
    @pytest.mark.parametrize("url,params", [
        (PAINEL_URL, {}), (VISAO_URL, {}), (EXPORT_URL, {"formato": "csv"}),
    ])
    def test_agricultor_nao_le(self, auth_client_sem_acesso, arvore, url, params):
        assert auth_client_sem_acesso.get(url, params).status_code == status.HTTP_403_FORBIDDEN

    def test_fgd_le_o_plano_inteiro(self, auth_client_fgd, arvore, municipio_ce):
        outro_territorio = WorkPlanAcaoFactory(
            meta=arvore["a1"].meta, submeta=arvore["s2"], numero="1.2.9", indicador=arvore["indicador"],
        )
        ActivityFactory(acao=outro_territorio, status="concluido", municipio=municipio_ce)

        painel = auth_client_fgd.get(PAINEL_URL)
        visao = auth_client_fgd.get(VISAO_URL)
        exportacao = auth_client_fgd.get(EXPORT_URL, {"formato": "csv"})

        ids = {acao["id"] for grupo in painel.data["metas"] for acao in grupo["acoes"]}
        assert {arvore["a1"].pk, arvore["a2"].pk, outro_territorio.pk} <= ids
        assert visao.data["indicadores"][0]["quantidade_realizada"] == "6.00"
        assert outro_territorio.descricao in exportacao.content.decode("utf-8-sig")


class TestAtividades:
    def test_cadeia_do_plano_de_trabalho_derivada_da_acao(self, auth_client, arvore):
        atividade = arvore["atividades"][0]

        lista = auth_client.get(ATIVIDADES_URL, {"page_size": 50})
        detalhe = auth_client.get(f"{ATIVIDADES_URL}{atividade.pk}/")

        item = next(a for a in lista.data["results"] if a["id"] == atividade.pk)
        for plano in (item["plano_trabalho"], detalhe.data["plano_trabalho"]):
            assert plano["meta"]["numero"] == 1
            assert plano["submeta"]["numero"] == "1.1"
            assert plano["acao"]["numero"] == "1.1.1"
            assert plano["indicador"]["codigo"] == "TST-OFI"

    def test_calendario_traz_a_cadeia(self, auth_client, arvore):
        response = auth_client.get(
            f"{ATIVIDADES_URL}calendario/", {"inicio": "2026-05-15", "fim": "2026-06-15"}
        )

        assert response.status_code == status.HTTP_200_OK
        itens = response.data["results"]
        assert len(itens) == 5
        assert {item["plano_trabalho"]["submeta"]["numero"] for item in itens} == {"1.1", "1.2"}

    @pytest.mark.parametrize("filtro", ["meta", "submeta", "indicador"])
    def test_filtros_da_hierarquia(self, auth_client, arvore, filtro):
        valor = {
            "meta": arvore["a1"].meta_id,
            "submeta": arvore["s2"].pk,
            "indicador": arvore["indicador"].pk,
        }[filtro]
        outra = ActivityFactory(acao=WorkPlanAcaoFactory(meta=WorkPlanMetaFactory(numero=3)))

        response = auth_client.get(ATIVIDADES_URL, {filtro: valor, "page_size": 50})

        ids = {item["id"] for item in response.data["results"]}
        assert outra.pk not in ids
        esperadas = 1 if filtro == "submeta" else 5
        assert len(ids) == esperadas
