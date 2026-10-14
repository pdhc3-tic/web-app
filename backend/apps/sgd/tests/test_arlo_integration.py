import csv
from decimal import Decimal
from io import StringIO
from uuid import uuid4

import pytest

from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification
from apps.core.signals.audit import get_audit_context
from apps.core.storage import get_storage
from apps.sgd import tasks as sgd_tasks
from apps.sgd.models import ArloFieldMapping, ArloImport, DemandDocument
from apps.sgd.services import arlo_export
from apps.sgd.services import balance as balance_service
from apps.sgd.services.arlo_import import processar_importacao
from apps.sgd.services.arlo_mapping import MAPEAMENTO_PADRAO
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.models import BudgetTransaction, GlosaRisk

pytestmark = pytest.mark.django_db

CABECALHO = "ID Demanda;ID Solicitação;Número do Processo;Data do Pagamento;Valor Pago;Comprovante"
COMPROVANTE = "https://arlo.example.com/comprovantes/123.pdf"


@pytest.fixture(autouse=True)
def storage_local(settings, tmp_path):
    settings.STORAGE_BACKEND = "local"
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def demanda_autorizada(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    return _autorizar(demand_request_rn, solicitante_rn)


def _autorizar(solicitacao, usuario, valor=Decimal("1000")):
    solicitacao.valor_estimado = valor
    solicitacao.valor_autorizado = valor
    solicitacao.save(update_fields=["valor_estimado", "valor_autorizado"])
    balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=usuario)
    demanda = solicitacao.demanda
    demanda.status = "autorizada"
    demanda.save(update_fields=["status"])
    return solicitacao


def _nova_demanda_autorizada(activity, solicitante, rubrica, valor=Decimal("500")):
    demanda = DemandFactory(activity=activity, solicitante=solicitante, status="rascunho")
    solicitacao = DemandRequestFactory(demanda=demanda, tipo="diaria", rubrica=rubrica, valor_estimado=valor)
    return _autorizar(solicitacao, solicitante, valor)


def _linha(solicitacao, valor="1000,00", processo="PROC-1", data="2026-09-10", comprovante=COMPROVANTE):
    return f"{solicitacao.demanda_id};{solicitacao.pk};{processo};{data};{valor};{comprovante}"


def _importar(linhas, usuario, nome="retorno.csv", ip=None):
    conteudo = "\n".join([CABECALHO, *linhas]).encode("utf-8")
    key = f"arlo/importacoes/{uuid4()}.csv"
    get_storage().save_from_bytes(key, conteudo)
    return ArloImport.objects.create(
        tipo="importacao", arquivo_key=key, arquivo_url=get_storage().get_public_url(key),
        nome_original=nome, operado_por=usuario, ip_origem=ip,
    )


def _ler_csv(conteudo: bytes):
    return list(csv.DictReader(StringIO(conteudo.decode("utf-8-sig"))))


# ---------- exportação ----------

def test_exportacao_gera_csv_com_todas_as_colunas(demanda_autorizada, activity_rn):
    conteudo, total = arlo_export.gerar_csv()
    linhas = _ler_csv(conteudo)

    assert total == 1 and len(linhas) == 1
    colunas = {item["coluna"] for item in MAPEAMENTO_PADRAO["exportacao"]}
    assert set(linhas[0]) == colunas
    for coluna in ("Meta", "Submeta", "Ação", "Indicador", "Atividade", "Rubrica"):
        assert linhas[0][coluna]
    acao = activity_rn.acao
    assert linhas[0]["Meta"].startswith(str(acao.meta.numero))
    assert linhas[0]["Indicador"].startswith(acao.indicador.codigo)
    assert linhas[0]["Atividade"] == activity_rn.titulo
    assert linhas[0]["Rubrica"] == "Diárias"
    assert linhas[0]["ID Demanda"] == str(demanda_autorizada.demanda_id)


def test_exportacao_so_inclui_demandas_autorizadas(demanda_autorizada, activity_rn, solicitante_rn, rubrica_diarias):
    DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")

    _, total = arlo_export.gerar_csv()

    assert total == 1


def test_mapeamento_configuravel_altera_colunas_exportadas(demanda_autorizada):
    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="demanda_id").update(coluna_arlo="Codigo Arlo")

    linhas = _ler_csv(arlo_export.gerar_csv()[0])

    assert "Codigo Arlo" in linhas[0] and "ID Demanda" not in linhas[0]


# ---------- importação ----------

def test_importacao_valida_conclui_demanda_e_cria_comprovante(demanda_autorizada, usuario_fgd):
    importacao = processar_importacao(_importar([_linha(demanda_autorizada)], usuario_fgd))

    demanda = demanda_autorizada.demanda
    demanda.refresh_from_db()
    assert demanda.status == "concluida"
    assert demanda.valor_pago_total == Decimal("1000.00")
    assert demanda.numero_processo == "PROC-1"
    comprovante = DemandDocument.objects.get(demanda=demanda, tipo="comprovante")
    assert comprovante.arquivo_url == COMPROVANTE and comprovante.enviado_por == usuario_fgd
    assert (importacao.total_registros, importacao.registros_ok, importacao.erros_json) == (1, 1, [])
    assert importacao.status == "concluido"
    # Passa por "Em atendimento" como no fluxo manual: etapa registrada e solicitante notificado.
    assert demanda.etapas.filter(etapa="atendimento", acao="atendido").count() == 2
    assert Notification.objects.filter(evento="demand_em_atendimento", user=demanda.solicitante).exists()
    assert Notification.objects.filter(evento="demand_concluida", user=demanda.solicitante).exists()


def test_linha_malformada_nao_interrompe_as_validas(
    demanda_autorizada, activity_rn, solicitante_rn, rubrica_diarias, usuario_fgd,
):
    outra = _nova_demanda_autorizada(activity_rn, solicitante_rn, rubrica_diarias)
    malformada = f"{demanda_autorizada.demanda_id};{demanda_autorizada.pk};PROC-1;2026-09-10;;{COMPROVANTE}"

    importacao = processar_importacao(
        _importar([malformada, _linha(outra, valor="500,00", processo="PROC-2")], usuario_fgd),
    )

    assert (importacao.total_registros, importacao.registros_ok) == (2, 1)
    assert [(e["linha"], e["campo"]) for e in importacao.erros_json] == [(2, "valor_pago")]
    demanda_autorizada.demanda.refresh_from_db()
    outra.demanda.refresh_from_db()
    assert demanda_autorizada.demanda.status == "autorizada"
    assert outra.demanda.status == "concluida"


def test_demanda_inexistente_reporta_erro_especifico(demanda_autorizada, usuario_fgd):
    linha = f"999999;;PROC-9;2026-09-10;100,00;{COMPROVANTE}"

    importacao = processar_importacao(_importar([linha], usuario_fgd))

    assert importacao.registros_ok == 0
    assert importacao.erros_json[0]["linha"] == 2
    assert importacao.erros_json[0]["campo"] == "demanda_id"
    assert "inexistente" in importacao.erros_json[0]["erro"]


def test_valor_pago_maior_registra_risco_de_glosa(demanda_autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn):
    importacao = processar_importacao(_importar([_linha(demanda_autorizada, valor="1200,00")], usuario_fgd))

    assert importacao.registros_ok == 1
    glosa = GlosaRisk.objects.get()
    assert (glosa.valor_autorizado, glosa.valor_pago, glosa.excedente) == (
        Decimal("1000.00"), Decimal("1200.00"), Decimal("200.00"),
    )
    assert glosa.demanda_id == str(demanda_autorizada.demanda_id) and glosa.criado_por == usuario_fgd
    demanda_autorizada.refresh_from_db()
    assert demanda_autorizada.valor_pago == Decimal("1200.00")
    # O excedente não estoura os limites: executa só o autorizado.
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_executado == Decimal("1000.00")
    assert allocation_territorial_rn.valor_executado == Decimal("1000.00")


def test_valor_pago_igual_ou_menor_nao_registra_glosa(demanda_autorizada, usuario_fgd):
    processar_importacao(_importar([_linha(demanda_autorizada, valor="900,00")], usuario_fgd))

    assert not GlosaRisk.objects.exists()


def test_valor_pago_menor_libera_diferenca_ao_limite_individual_e_ao_pool(
    demanda_autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    assert allocation_territorial_rn.valor_comprometido == Decimal("1000")

    processar_importacao(_importar([_linha(demanda_autorizada, valor="800,00")], usuario_fgd))

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado) == (
        Decimal("0"), Decimal("800"),
    )
    assert (allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado) == (
        Decimal("0"), Decimal("800"),
    )
    assert limite_individual_rn.saldo_disponivel == limite_individual_rn.valor_limite - Decimal("800")
    assert BudgetTransaction.objects.filter(
        demanda_id=str(demanda_autorizada.pk), tipo="liberacao", valor=Decimal("200"),
    ).exists()


def test_reimportar_mesma_solicitacao_e_recusado(demanda_autorizada, usuario_fgd):
    processar_importacao(_importar([_linha(demanda_autorizada)], usuario_fgd))

    segunda = processar_importacao(_importar([_linha(demanda_autorizada)], usuario_fgd))

    assert segunda.registros_ok == 0 and len(segunda.erros_json) == 1


def test_planilha_sem_coluna_obrigatoria_falha_o_arquivo(demanda_autorizada, usuario_fgd):
    key = f"arlo/importacoes/{uuid4()}.csv"
    get_storage().save_from_bytes(key, b"ID Demanda;Valor Pago\n1;10")
    importacao = ArloImport.objects.create(
        tipo="importacao", arquivo_key=key, arquivo_url="http://x/y", nome_original="r.csv", operado_por=usuario_fgd,
    )

    processar_importacao(importacao)

    importacao.refresh_from_db()
    assert importacao.status == "falhou" and "ausentes" in importacao.erros_json[0]["erro"]


def test_movimentacoes_da_importacao_herdam_usuario_e_ip_do_envio(demanda_autorizada, usuario_fgd):
    processar_importacao(_importar([_linha(demanda_autorizada, valor="800,00")], usuario_fgd, ip="203.0.113.7"))

    logs = AuditLog.objects.filter(acao__in=["execucao", "arlo_pagamento"], entidade_id=str(demanda_autorizada.pk))
    assert {log.acao for log in logs} == {"execucao", "arlo_pagamento"}
    assert all(log.ip == "203.0.113.7" and log.user == usuario_fgd for log in logs)
    assert get_audit_context()["ip"] is None  # contexto não vaza para a thread


# ---------- task, API e histórico ----------

def test_task_process_arlo_import_processa_e_e_idempotente(demanda_autorizada, usuario_fgd):
    importacao = _importar([_linha(demanda_autorizada)], usuario_fgd)

    assert sgd_tasks.process_arlo_import(importacao.pk) == 1
    assert sgd_tasks.process_arlo_import(importacao.pk) == 0  # já processada
    assert sgd_tasks.process_arlo_import.queue == "normal"


def test_historico_reflete_exportacao_e_importacao(
    auth_client_fgd, demanda_autorizada, usuario_fgd, monkeypatch, django_capture_on_commit_callbacks,
):
    monkeypatch.setattr(sgd_tasks.process_arlo_import, "delay", lambda pk: sgd_tasks.process_arlo_import(pk))

    resposta = auth_client_fgd.post("/api/v1/sgd/arlo/exportar/")
    assert resposta.status_code == 200
    assert len(_ler_csv(resposta.content)) == 1

    key = f"arlo/importacoes/{uuid4()}.csv"
    get_storage().save_from_bytes(key, "\n".join([CABECALHO, _linha(demanda_autorizada)]).encode("utf-8"))
    with django_capture_on_commit_callbacks(execute=True):
        resposta = auth_client_fgd.post(
            "/api/v1/sgd/arlo/importar/", {"key": key, "nome_original": "retorno.csv"}, format="json",
        )
    assert resposta.status_code == 202
    assert ArloImport.objects.get(tipo="importacao").ip_origem == "127.0.0.1"

    historico = auth_client_fgd.get("/api/v1/sgd/arlo/").json()
    por_tipo = {item["tipo"]: item for item in historico}
    assert set(por_tipo) == {"exportacao", "importacao"}
    assert (por_tipo["exportacao"]["total_registros"], por_tipo["exportacao"]["registros_ok"]) == (1, 1)
    assert (por_tipo["importacao"]["total_registros"], por_tipo["importacao"]["registros_ok"]) == (1, 1)
    assert por_tipo["importacao"]["operado_por"] == usuario_fgd.pk
    assert por_tipo["importacao"]["status"] == "concluido"
    assert por_tipo["importacao"]["nome_original"] == "retorno.csv"
    assert por_tipo["exportacao"]["arquivo_url"]


def test_exportar_e_importar_exigem_perfil_fgd(auth_client_ugp, auth_client_solicitante):
    assert auth_client_ugp.post("/api/v1/sgd/arlo/exportar/").status_code == 403
    assert auth_client_solicitante.post("/api/v1/sgd/arlo/exportar/").status_code == 403
    assert auth_client_solicitante.get("/api/v1/sgd/arlo/").status_code == 403
