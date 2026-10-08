"""Massa de dados do SGD criada pelo `seed_demo`: um caso por critério de aceitação."""
from datetime import datetime, timezone as fuso

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.core.models import PowerBIToken
from apps.sgd.models import ApprovalStep, ArloImport, Demand, DemandRequest
from apps.sgd.models.demand import STATUS_CHOICES
from apps.sgd.services.approval import alerta_rubrica_fora_do_previsto, demand_visibility_scope
from apps.sgd.tasks import DIAS_UTEIS_LIMITE, _dias_uteis_entre
from apps.sgp.cache import get_power_bi_snapshot
from apps.sgp.management.commands.seed_demo import SUPER_ADMIN, email_de_demo
from apps.sgp.models import GoogleCalendarSyncEvent

User = get_user_model()

pytestmark = pytest.mark.django_db

TITULO_DEMANDA_PARADA = "Material de divulgação do seminário territorial"
STATUS_JA_EXECUTADA = ["em_andamento", "concluido", "concluido_sem_evidencia"]


def rodar_seed(reset=False):
    call_command("seed_core")
    opcoes = {"reset": True} if reset else {}
    call_command("seed_demo", "--no-files", "--upfs", "8", "--atividades", "6", **opcoes)


@pytest.fixture
def seed():
    rodar_seed()


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


def test_existe_demanda_em_cada_um_dos_nove_estados(seed):
    esperados = {status for status, _ in STATUS_CHOICES}
    assert len(esperados) == 9
    assert set(Demand.objects.values_list("status", flat=True)) >= esperados


def test_existe_remanejamento_emergencial_com_excedente_autorizado(seed):
    etapa = ApprovalStep.objects.filter(excedente_autorizado=True).exclude(justificativa="").get()
    assert etapa.etapa == "autorizacao"
    assert "emergencial" in etapa.justificativa.lower()
    assert etapa.demanda.status == "autorizada"


def test_existe_solicitacao_com_rubrica_fora_das_previstas_da_acao(seed):
    solicitacoes = list(DemandRequest.objects.select_related("demanda__activity__acao"))
    fora = [s for s in solicitacoes if alerta_rubrica_fora_do_previsto(s)]
    assert fora
    assert len(fora) < len(solicitacoes)


def test_demandas_em_duas_ufs_com_solicitantes_distintos(seed):
    por_uf = {}
    for demanda in Demand.objects.select_related("activity__municipio__state"):
        por_uf.setdefault(demanda.activity.municipio.state.sigla, set()).add(demanda.solicitante_id)

    assert set(por_uf) >= {"PE", "RN"}
    assert por_uf["PE"].isdisjoint(por_uf["RN"])


def test_articulador_so_enxerga_as_demandas_submetidas_do_proprio_estado(seed):
    articulador_pe = User.objects.get(email=email_de_demo("Sandra", "Queiroz"))

    visiveis = Demand.objects.filter(demand_visibility_scope(articulador_pe), status="submetida")

    assert visiveis.exists()
    assert {d.activity.municipio.state.sigla for d in visiveis} == {"PE"}


def test_demanda_concluida_vinculada_a_atividade_sem_evidencia(seed):
    demanda = Demand.objects.get(status="concluida")
    assert demanda.activity.status == "concluido_sem_evidencia"


def test_despesa_posterior_sinalizada_em_atividade_ja_executada(seed):
    demandas = Demand.objects.filter(despesa_posterior=True, activity__status__in=STATUS_JA_EXECUTADA)
    assert demandas.exists()
    assert all(d.justificativa for d in demandas)


@pytest.mark.parametrize("hoje", [
    datetime(2026, 3, 10, 12, 0, tzinfo=fuso.utc),
    datetime(2026, 10, 3, 12, 0, tzinfo=fuso.utc),
])
def test_demanda_parada_continua_acima_do_limite_de_dias_uteis(hoje):
    from unittest.mock import patch

    with patch("django.utils.timezone.now", return_value=hoje):
        rodar_seed()
        parada = Demand.objects.get(titulo=TITULO_DEMANDA_PARADA)

    assert parada.status == "submetida"
    assert parada.status_alterado_em < hoje
    assert all(a.operado_em < hoje for a in ArloImport.objects.all())
    assert _dias_uteis_entre(parada.status_alterado_em.date(), hoje.date(), uf="PE") >= DIAS_UTEIS_LIMITE


def test_token_do_power_bi_ativo_e_snapshot_em_dia(seed):
    assert PowerBIToken.objects.filter(ativo=True).count() == 1
    assert get_power_bi_snapshot() is not None

    admin = User.objects.get(email=email_de_demo(*SUPER_ADMIN))
    resposta = _cliente(admin).get("/api/v1/admin/power-bi-token/")

    assert resposta.status_code == 200
    assert resposta.data["token_mascarado"]
    assert resposta.data["status_snapshot"] == "em_dia"


def test_eventos_do_google_calendar_cobrem_os_quatro_campos_do_status(seed):
    assert GoogleCalendarSyncEvent.objects.count() == 4

    admin = User.objects.get(email=email_de_demo(*SUPER_ADMIN))
    resposta = _cliente(admin).get("/api/v1/core/config/google-calendar/status/")

    assert resposta.status_code == 200
    assert resposta.data["estado"] == "ok"
    assert resposta.data["ultima_sincronizacao"] is not None
    assert resposta.data["ultimo_erro"] == "Token do Google Calendar expirado."
    assert resposta.data["falhas_recentes"] == 2


def test_reset_recria_o_seed_do_sgd_sem_duplicar():
    rodar_seed()
    total = Demand.objects.count()

    rodar_seed(reset=True)

    assert Demand.objects.count() == total
    assert PowerBIToken.objects.count() == 1
    assert GoogleCalendarSyncEvent.objects.count() == 4
    assert ArloImport.objects.count() == 3
    assert {s for s in Demand.objects.values_list("status", flat=True)} >= {s for s, _ in STATUS_CHOICES}


def test_existe_importacao_do_arlo_com_erros_e_outra_sem(seed):
    importacoes = ArloImport.objects.filter(tipo=ArloImport.Tipo.IMPORTACAO)

    assert importacoes.exclude(erros_json=[]).exists()
    assert importacoes.filter(erros_json=[]).exists()


def test_historico_do_arlo_e_coerente(seed):
    assert ArloImport.objects.filter(tipo=ArloImport.Tipo.EXPORTACAO).count() == 1
    for registro in ArloImport.objects.filter(status=ArloImport.Status.CONCLUIDO):
        assert registro.registros_ok + len(registro.erros_json) == registro.total_registros
        assert registro.operado_por is not None
        assert registro.arquivo_url.endswith(registro.arquivo_key)
        for erro in registro.erros_json:
            assert {"linha", "erro", "campo"} <= set(erro)


def test_exportacao_do_arlo_conta_as_solicitacoes_das_demandas_autorizadas(seed):
    exportacao = ArloImport.objects.get(tipo=ArloImport.Tipo.EXPORTACAO)

    autorizadas = DemandRequest.objects.filter(demanda__status="autorizada").count()

    assert exportacao.total_registros == exportacao.registros_ok == autorizadas > 0


def test_erro_do_arlo_aponta_para_a_demanda_recusada_do_seed(seed):
    recusada = Demand.objects.get(status="recusada")
    com_erros = ArloImport.objects.exclude(erros_json=[]).get()

    assert any(f"#{recusada.pk} " in erro["erro"] for erro in com_erros.erros_json)
