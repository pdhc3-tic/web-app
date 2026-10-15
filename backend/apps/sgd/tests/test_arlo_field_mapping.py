from uuid import uuid4

import pytest

from apps.core.models.audit_log import AuditLog
from apps.core.storage import get_storage
from apps.sgd.models import ArloFieldMapping, ArloImport
from apps.sgd.services import arlo_export
from apps.sgd.services.arlo_import import processar_importacao
from apps.sgd.services.arlo_mapping import MAPEAMENTO_PADRAO, obter_mapeamento

# Fixtures e helpers compartilhados com a suíte de integração Arlo.
from apps.sgd.tests.test_arlo_integration import (  # noqa: F401
    CABECALHO, _importar, _ler_csv, _linha, demanda_autorizada, storage_local,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/config/arlo-mapping/"


def _linha_mapeamento(direcao, campo):
    return ArloFieldMapping.objects.get(direcao=direcao, campo_sgd=campo)


# ---------- CRUD ----------

def test_migration_semeia_o_mapeamento_padrao():
    colunas = [m.coluna_arlo for m in ArloFieldMapping.objects.filter(direcao="exportacao").order_by("ordem")]
    assert colunas == [item["coluna"] for item in MAPEAMENTO_PADRAO["exportacao"]]
    assert ArloFieldMapping.objects.filter(direcao="importacao").count() == len(MAPEAMENTO_PADRAO["importacao"])


def test_super_admin_lista_filtrando_por_direcao(auth_client_super_admin):
    resposta = auth_client_super_admin.get(URL, {"direcao": "importacao"})

    assert resposta.status_code == 200
    assert {m["direcao"] for m in resposta.json()} == {"importacao"}


def test_criar_editar_e_remover_coluna(auth_client_super_admin):
    criada = auth_client_super_admin.post(
        URL, {"direcao": "exportacao", "campo_sgd": "solicitante", "coluna_arlo": "Solicitante"}, format="json",
    )
    assert criada.status_code == 201
    corpo = criada.json()
    assert corpo["formato"] == "texto"
    assert corpo["ordem"] == len(MAPEAMENTO_PADRAO["exportacao"]) + 1  # entra no fim

    editada = auth_client_super_admin.patch(f"{URL}{corpo['id']}/", {"coluna_arlo": "Requerente"}, format="json")
    assert editada.status_code == 200 and editada.json()["coluna_arlo"] == "Requerente"

    assert auth_client_super_admin.delete(f"{URL}{corpo['id']}/").status_code == 204
    assert not ArloFieldMapping.objects.filter(pk=corpo["id"]).exists()
    assert set(
        AuditLog.objects.filter(entidade="ArloFieldMapping").values_list("acao", flat=True)
    ) == {"arlo_mapping.criado", "arlo_mapping.alterado", "arlo_mapping.removido"}


def test_direcao_e_campo_nao_mudam_depois_de_criados(auth_client_super_admin):
    linha = _linha_mapeamento("exportacao", "titulo")

    auth_client_super_admin.patch(f"{URL}{linha.pk}/", {"campo_sgd": "meta", "direcao": "importacao"}, format="json")

    linha.refresh_from_db()
    assert (linha.direcao, linha.campo_sgd) == ("exportacao", "titulo")


def test_reordenar_colunas(auth_client_super_admin):
    ids = list(
        ArloFieldMapping.objects.filter(direcao="exportacao").order_by("ordem").values_list("pk", flat=True)
    )
    nova_ordem = list(reversed(ids))

    resposta = auth_client_super_admin.post(
        f"{URL}reordenar/", {"direcao": "exportacao", "ids": nova_ordem}, format="json",
    )

    assert resposta.status_code == 200
    assert [m["id"] for m in resposta.json()] == nova_ordem
    assert [m["campo"] for m in obter_mapeamento()["exportacao"]][0] == "valor_autorizado"


def test_reordenar_exige_todos_os_ids_da_direcao(auth_client_super_admin):
    ids = list(ArloFieldMapping.objects.filter(direcao="exportacao").values_list("pk", flat=True))

    resposta = auth_client_super_admin.post(
        f"{URL}reordenar/", {"direcao": "exportacao", "ids": ids[:-1]}, format="json",
    )

    assert resposta.status_code == 400


def test_campo_obrigatorio_nao_pode_ser_desativado_nem_removido(auth_client_super_admin):
    linha = _linha_mapeamento("exportacao", "rubrica")

    assert auth_client_super_admin.patch(f"{URL}{linha.pk}/", {"ativo": False}, format="json").status_code == 400
    assert auth_client_super_admin.delete(f"{URL}{linha.pk}/").status_code == 400
    assert ArloFieldMapping.objects.get(pk=linha.pk).ativo is True


def test_campo_opcional_pode_ser_desativado(auth_client_super_admin):
    linha = _linha_mapeamento("exportacao", "titulo")

    resposta = auth_client_super_admin.patch(f"{URL}{linha.pk}/", {"ativo": False}, format="json")

    assert resposta.status_code == 200
    assert "titulo" not in [m["campo"] for m in obter_mapeamento()["exportacao"]]


def test_validacoes_de_campo_formato_e_coluna(auth_client_super_admin):
    base = {"direcao": "exportacao", "campo_sgd": "solicitante", "coluna_arlo": "Solicitante"}

    assert auth_client_super_admin.post(URL, {**base, "campo_sgd": "inexistente"}, format="json").status_code == 400
    assert auth_client_super_admin.post(URL, {**base, "formato": "data"}, format="json").status_code == 400
    # coluna já usada por outro campo na mesma direção
    assert auth_client_super_admin.post(URL, {**base, "coluna_arlo": "Meta"}, format="json").status_code == 400
    # campo já mapeado na direção
    assert auth_client_super_admin.post(
        URL, {**base, "campo_sgd": "meta", "coluna_arlo": "Outra"}, format="json",
    ).status_code == 400


@pytest.mark.parametrize("cliente", ["auth_client_fgd", "auth_client_ugp", "auth_client_solicitante"])
def test_nao_super_admin_recebe_403(cliente, request):
    client = request.getfixturevalue(cliente)
    linha = _linha_mapeamento("exportacao", "titulo")

    assert client.get(URL).status_code == 403
    assert client.post(URL, {}, format="json").status_code == 403
    assert client.patch(f"{URL}{linha.pk}/", {"coluna_arlo": "X"}, format="json").status_code == 403
    assert client.delete(f"{URL}{linha.pk}/").status_code == 403
    assert client.post(f"{URL}reordenar/", {}, format="json").status_code == 403


def test_anonimo_nao_acessa(api_client):
    assert api_client.get(URL).status_code in (401, 403)


# ---------- exportação ----------

def test_exportacao_reflete_nome_e_ordem_configurados(demanda_autorizada):
    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="demanda_id").update(
        coluna_arlo="Codigo Arlo", ordem=99,
    )
    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="rubrica").update(ordem=0)
    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="titulo").update(ativo=False)

    conteudo, _ = arlo_export.gerar_csv()
    cabecalho = conteudo.decode("utf-8-sig").splitlines()[0].split(",")

    assert cabecalho[0] == "Rubrica" and cabecalho[-1] == "Codigo Arlo"
    assert "Título" not in cabecalho and "ID Demanda" not in cabecalho


def test_exportacao_aplica_formato_de_moeda(demanda_autorizada):
    linhas = _ler_csv(arlo_export.gerar_csv()[0])
    assert linhas[0]["Valor Autorizado"] == "1000,00"

    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="valor_autorizado").update(formato="texto")
    linhas = _ler_csv(arlo_export.gerar_csv()[0])
    assert linhas[0]["Valor Autorizado"] == "1000.00"


# ---------- importação ----------

def test_importacao_interpreta_planilha_conforme_mapeamento_vigente(demanda_autorizada, usuario_fgd):
    for campo, coluna in {"numero_processo": "Processo Arlo", "valor_pago": "Total Pago"}.items():
        ArloFieldMapping.objects.filter(direcao="importacao", campo_sgd=campo).update(coluna_arlo=coluna)
    cabecalho = CABECALHO.replace("Número do Processo", "Processo Arlo").replace("Valor Pago", "Total Pago")
    conteudo = "\n".join([cabecalho, _linha(demanda_autorizada, processo="PROC-9")]).encode("utf-8")
    key = f"arlo/importacoes/{uuid4()}.csv"
    get_storage().save_from_bytes(key, conteudo)
    importacao = ArloImport.objects.create(
        tipo="importacao", arquivo_key=key, arquivo_url="http://x/y", nome_original="r.csv", operado_por=usuario_fgd,
    )

    processar_importacao(importacao)

    importacao.refresh_from_db()
    assert (importacao.status, importacao.registros_ok, importacao.erros_json) == ("concluido", 1, [])
    demanda_autorizada.demanda.refresh_from_db()
    assert demanda_autorizada.demanda.numero_processo == "PROC-9"


def test_planilha_com_nome_antigo_de_coluna_falha_apos_renomear(demanda_autorizada, usuario_fgd):
    ArloFieldMapping.objects.filter(direcao="importacao", campo_sgd="valor_pago").update(coluna_arlo="Total Pago")

    importacao = processar_importacao(_importar([_linha(demanda_autorizada)], usuario_fgd))

    assert importacao.status == "falhou" and "Total Pago" in importacao.erros_json[0]["erro"]


# ---------- histórico ----------

def test_historico_preserva_o_mapeamento_vigente_na_operacao(
    demanda_autorizada, usuario_fgd, auth_client_fgd,
):
    exportacao, _ = arlo_export.exportar(usuario=usuario_fgd)
    importacao = processar_importacao(_importar([_linha(demanda_autorizada)], usuario_fgd))
    assert importacao.status == "concluido"
    antes_exp = exportacao.mapeamento_snapshot
    antes_imp = ArloImport.objects.get(pk=importacao.pk).mapeamento_snapshot
    assert antes_exp["exportacao"][0] == {"campo": "demanda_id", "coluna": "ID Demanda", "formato": "texto"}
    assert antes_imp["importacao"]["valor_pago"] == {"coluna": "Valor Pago", "formato": "moeda"}

    # Super Admin muda o mapeamento depois das operações.
    ArloFieldMapping.objects.filter(direcao="exportacao", campo_sgd="demanda_id").update(coluna_arlo="Codigo Arlo")
    ArloFieldMapping.objects.filter(direcao="importacao", campo_sgd="valor_pago").update(coluna_arlo="Total Pago")

    historico = {item["id"]: item for item in auth_client_fgd.get("/api/v1/sgd/arlo/").json()}
    assert historico[exportacao.pk]["mapeamento_snapshot"] == antes_exp
    assert historico[importacao.pk]["mapeamento_snapshot"] == antes_imp
    assert historico[importacao.pk]["status"] == "concluido"
    detalhe = auth_client_fgd.get(f"/api/v1/sgd/arlo/{exportacao.pk}/")
    assert detalhe.status_code == 200 and detalhe.json()["mapeamento_snapshot"] == antes_exp
