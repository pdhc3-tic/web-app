"""Campos de anexo no catálogo de tipos: o valor é o id de um documento da demanda,
enviado pelo fluxo de documentos com `tipo="anexo"`, e fica ligado à solicitação e ao campo."""
from unittest.mock import patch

import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models import DemandDocument, TipoSolicitacao
from apps.sgd.services import demand as demand_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.anexos import campos_de_anexo, ids_do_campo
from apps.sgd.services.demand_document import documentos_no_limite, exigir_pode_gerenciar_documento
from apps.sgd.tests.factories import DemandDocumentFactory, DemandFactory, TipoSolicitacaoFactory

pytestmark = pytest.mark.django_db

URL_CATALOGO = "/api/v1/sgd/config/tipos-solicitacao/"
SCHEMA_COM_ANEXOS = {
    "type": "object",
    "required": ["arte"],
    "properties": {
        "descricao": {"type": "string"},
        "arte": {"type": "integer", "format": "anexo", "title": "Arte"},
        "cotacoes": {
            "type": "array", "items": {"type": "integer", "format": "anexo"}, "minItems": 3, "title": "Cotações",
        },
    },
}


@pytest.fixture
def tipo_com_anexos(db, rubrica_diarias):
    return TipoSolicitacaoFactory(slug="material-com-arte", rubrica=rubrica_diarias, schema_campos=SCHEMA_COM_ANEXOS)


def _anexo(demand, nome_original="arte.pdf", **kwargs):
    return DemandDocumentFactory(demanda=demand, tipo="anexo", fornecedor="", nome_original=nome_original, **kwargs)


def _url_solicitacoes(demand):
    return f"/api/v1/sgd/demandas/{demand.pk}/solicitacoes/"


def _criar(client, demand, campos):
    return client.post(_url_solicitacoes(demand), {
        "tipo": "material-com-arte", "campos_json": campos, "valor_estimado": "300.00",
    }, format="json")


def _download(demand, documento):
    return f"/api/v1/sgd/demandas/{demand.pk}/documentos/{documento.pk}/download/"


# ---------- Declaração no catálogo ----------

def test_campos_de_anexo_le_um_arquivo_e_varios():
    assert campos_de_anexo(SCHEMA_COM_ANEXOS) == {"arte": False, "cotacoes": True}
    assert campos_de_anexo({"type": "object"}) == {}


@pytest.mark.parametrize("valor, multiplo, esperado", [
    (None, False, []), ("", False, []), ([], True, []),
    (7, False, [7]), ([7, 8], True, [7, 8]),
    ([7], False, None), (7, True, None), ("7", False, None), (True, False, None), ([7, "8"], True, None),
])
def test_ids_do_campo_so_aceita_a_forma_do_campo(valor, multiplo, esperado):
    assert ids_do_campo(valor, multiplo=multiplo) == esperado


def test_catalogo_aceita_campo_de_anexo_inteiro_ou_lista(auth_client_super_admin, rubrica_diarias):
    resp = auth_client_super_admin.post(URL_CATALOGO, {
        "slug": "com-anexo", "nome": "Com anexo", "rubrica": rubrica_diarias.pk, "schema_campos": SCHEMA_COM_ANEXOS,
    }, format="json")

    assert resp.status_code == 201, resp.data


@pytest.mark.parametrize("declaracao", [
    {"type": "string", "format": "anexo"},
    {"format": "anexo"},
    {"type": "array", "items": {"type": "string", "format": "anexo"}},
])
def test_catalogo_recusa_campo_de_anexo_que_nao_guarda_id(auth_client_super_admin, rubrica_diarias, declaracao):
    resp = auth_client_super_admin.post(URL_CATALOGO, {
        "slug": "com-anexo", "nome": "Com anexo", "rubrica": rubrica_diarias.pk,
        "schema_campos": {"type": "object", "properties": {"arte": declaracao}},
    }, format="json")

    assert resp.status_code == 400
    assert "arte" in str(resp.data["schema_campos"])


# ---------- Upload ----------

def test_solicitante_envia_anexo_com_a_demanda_editavel(demand_rascunho_rn, solicitante_rn):
    exigir_pode_gerenciar_documento(demand_rascunho_rn, solicitante_rn, "anexo")


# ---------- Gravação ----------

def test_campo_de_um_arquivo_liga_o_documento_e_devolve_nome_e_link(
    auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk})

    assert resp.status_code == 201, resp.data
    arte.refresh_from_db()
    assert (arte.solicitacao_id, arte.campo) == (resp.data["id"], "arte")
    assert resp.data["campos_json"]["arte"] == arte.pk
    assert resp.data["anexos"] == {
        "arte": {"id": arte.pk, "nome_original": "arte.pdf", "download": _download(demand_rascunho_rn, arte)},
        "cotacoes": [],
    }


def test_campo_de_varios_arquivos_mantem_a_ordem_informada(
    auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)
    cotacoes = [_anexo(demand_rascunho_rn, nome_original=f"cotacao-{n}.pdf") for n in range(3)]
    ordem = [cotacoes[2].pk, cotacoes[0].pk, cotacoes[1].pk]

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk, "cotacoes": ordem})

    assert resp.status_code == 201, resp.data
    assert [item["id"] for item in resp.data["anexos"]["cotacoes"]] == ordem
    assert set(
        DemandDocument.objects.filter(pk__in=ordem).values_list("solicitacao_id", "campo")
    ) == {(resp.data["id"], "cotacoes")}


def test_minimo_de_arquivos_vem_do_schema(auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos):
    arte = _anexo(demand_rascunho_rn)
    cotacoes = [_anexo(demand_rascunho_rn).pk for _ in range(2)]

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk, "cotacoes": cotacoes})

    assert resp.status_code == 400
    assert "cotacoes" in resp.data


def test_anexo_obrigatorio_sem_arquivo_e_recusado(auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos):
    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"descricao": "Banner"})

    assert resp.status_code == 400
    assert "arte" in resp.data["campos_json"][0]


def test_lista_de_anexos_obrigatoria_nao_aceita_lista_vazia(
    auth_client_solicitante, demand_rascunho_rn, rubrica_diarias,
):
    TipoSolicitacaoFactory(slug="material-com-arte", rubrica=rubrica_diarias, schema_campos={
        "type": "object", "required": ["cotacoes"],
        "properties": {"cotacoes": {"type": "array", "items": {"type": "integer", "format": "anexo"}}},
    })

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"cotacoes": []})

    assert resp.status_code == 400
    assert resp.data["cotacoes"] == ["Obrigatório."]


@pytest.mark.parametrize("documento", [
    "de_outra_demanda", "inativo", "de_outro_tipo", "inexistente",
])
def test_documento_que_nao_e_anexo_desta_demanda_e_recusado(
    auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos, documento,
):
    criar = {
        "de_outra_demanda": lambda: _anexo(DemandFactory()).pk,
        "inativo": lambda: _anexo(demand_rascunho_rn, ativo=False).pk,
        "de_outro_tipo": lambda: DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="suporte").pk,
        "inexistente": lambda: 999_999,
    }

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": criar[documento]()})

    assert resp.status_code == 400
    assert resp.data["code"] == "BUSINESS_RULE"
    assert "arte" in resp.data
    assert not demand_rascunho_rn.solicitacoes.exists()


def test_anexo_de_outra_solicitacao_e_recusado(auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos):
    arte = _anexo(demand_rascunho_rn)
    assert _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk}).status_code == 201

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk})

    assert resp.status_code == 400
    assert "arte" in resp.data


def test_mesmo_documento_em_dois_campos_e_recusado(auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos):
    arte = _anexo(demand_rascunho_rn)
    outras = [_anexo(demand_rascunho_rn).pk for _ in range(2)]

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk, "cotacoes": [*outras, arte.pk]})

    assert resp.status_code == 400
    assert "cotacoes" in resp.data


def test_trocar_o_arquivo_remove_o_anterior(
    auth_client_solicitante, demand_rascunho_rn, solicitante_rn, tipo_com_anexos,
):
    antiga, nova = _anexo(demand_rascunho_rn), _anexo(demand_rascunho_rn)
    solicitacao_id = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": antiga.pk}).data["id"]

    resp = auth_client_solicitante.patch(
        f"{_url_solicitacoes(demand_rascunho_rn)}{solicitacao_id}/", {"campos_json": {"arte": nova.pk}}, format="json",
    )

    assert resp.status_code == 200, resp.data
    antiga.refresh_from_db()
    nova.refresh_from_db()
    assert not antiga.ativo
    assert (nova.solicitacao_id, nova.campo, nova.ativo) == (solicitacao_id, "arte", True)
    assert AuditLog.objects.filter(
        acao="demand_document.deleted", valores_anteriores__doc_id=antiga.pk, user=solicitante_rn,
    ).exists()


def test_remover_a_solicitacao_remove_os_anexos_dela(
    auth_client_solicitante, demand_rascunho_rn, solicitante_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)
    solicitacao_id = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk}).data["id"]

    resp = auth_client_solicitante.delete(f"{_url_solicitacoes(demand_rascunho_rn)}{solicitacao_id}/")

    assert resp.status_code == 204
    arte.refresh_from_db()
    assert not arte.ativo
    assert AuditLog.objects.filter(
        acao="demand_document.deleted", valores_anteriores__doc_id=arte.pk, user=solicitante_rn,
    ).exists()


# ---------- Limite de documentos ----------

def test_anexo_informado_num_campo_nao_conta_no_limite(
    auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)
    cotacoes = [_anexo(demand_rascunho_rn).pk for _ in range(3)]
    _anexo(demand_rascunho_rn)  # enviado e ainda não informado em campo nenhum
    DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="suporte")
    assert documentos_no_limite(demand_rascunho_rn) == 6

    resp = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk, "cotacoes": cotacoes})

    assert resp.status_code == 201, resp.data
    assert documentos_no_limite(demand_rascunho_rn) == 2


# ---------- Submissão e leitura ----------

def test_submissao_com_anexo_removido_aponta_o_campo_e_a_solicitacao(
    auth_client_solicitante, demand_rascunho_rn, solicitante_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)
    _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk})
    resp = auth_client_solicitante.delete(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/documentos/{arte.pk}/")
    assert resp.status_code == 204

    with pytest.raises(RegraDeNegocio) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    assert excinfo.value.campo == "arte"
    assert '"Arte"' in excinfo.value.mensagem
    assert tipo_com_anexos.nome in excinfo.value.mensagem
    demand_rascunho_rn.refresh_from_db()
    assert demand_rascunho_rn.status == "rascunho"


def test_anexo_removido_enquanto_a_submissao_espera_o_lock_barra_a_submissao(
    auth_client_solicitante, demand_rascunho_rn, solicitante_rn, tipo_com_anexos,
    allocation_territorial_rn, limite_individual_rn,
):
    arte = _anexo(demand_rascunho_rn)
    _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk})
    travar = workflow_service._travar_demanda

    def remover_antes_do_lock(demand, retrato=None):
        DemandDocument.objects.filter(pk=arte.pk).update(ativo=False)
        travar(demand, retrato)

    with patch.object(workflow_service, "_travar_demanda", side_effect=remover_antes_do_lock):
        with pytest.raises(RegraDeNegocio) as excinfo:
            demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    assert excinfo.value.campo == "arte"
    demand_rascunho_rn.refresh_from_db()
    assert demand_rascunho_rn.status == "rascunho"


def test_documento_nao_sai_de_demanda_ja_submetida(auth_client_solicitante, demand_rascunho_rn):
    arte = _anexo(demand_rascunho_rn)
    type(demand_rascunho_rn).objects.filter(pk=demand_rascunho_rn.pk).update(status="submetida")

    resp = auth_client_solicitante.delete(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/documentos/{arte.pk}/")

    assert resp.status_code == 403
    arte.refresh_from_db()
    assert arte.ativo


# ---------- Schema do catálogo alterado depois da gravação ----------

@pytest.mark.parametrize("campo, novo_schema_do_campo, valor_gravado", [
    ("arte", {"type": "array", "items": {"type": "integer", "format": "anexo"}}, "id"),
    ("cotacoes", {"type": "integer", "format": "anexo"}, "lista"),
])
def test_schema_alterado_nao_derruba_a_leitura_e_barra_a_submissao(
    auth_client_solicitante, demand_rascunho_rn, solicitante_rn, tipo_com_anexos,
    campo, novo_schema_do_campo, valor_gravado,
):
    arte = _anexo(demand_rascunho_rn)
    cotacoes = [_anexo(demand_rascunho_rn).pk for _ in range(3)]
    _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk, "cotacoes": cotacoes})
    schema = {**SCHEMA_COM_ANEXOS, "properties": {**SCHEMA_COM_ANEXOS["properties"], campo: novo_schema_do_campo}}
    TipoSolicitacao.objects.filter(pk=tipo_com_anexos.pk).update(schema_campos=schema)

    detalhe = auth_client_solicitante.get(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/")
    lista = auth_client_solicitante.get("/api/v1/sgd/demandas/")

    assert detalhe.status_code == 200
    assert lista.status_code == 200
    anexos = detalhe.data["solicitacoes"][0]["anexos"]
    assert anexos[campo] == ([] if valor_gravado == "id" else None)
    with pytest.raises(RegraDeNegocio) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)
    assert excinfo.value.campo == campo


def test_leitura_omite_anexo_removido(auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos):
    arte = _anexo(demand_rascunho_rn)
    _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk})
    DemandDocument.objects.filter(pk=arte.pk).update(ativo=False)

    lista = auth_client_solicitante.get(_url_solicitacoes(demand_rascunho_rn))
    detalhe = auth_client_solicitante.get(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/")

    assert lista.data[0]["anexos"]["arte"] is None
    assert detalhe.data["solicitacoes"][0]["anexos"]["arte"] is None


def test_tipo_sem_campo_de_anexo_devolve_anexos_vazio(demand_request_rn, auth_client_solicitante):
    resp = auth_client_solicitante.get(_url_solicitacoes(demand_request_rn.demanda))

    assert resp.data[0]["anexos"] == {}


def test_lista_de_documentos_mostra_a_solicitacao_e_o_campo(
    auth_client_solicitante, demand_rascunho_rn, tipo_com_anexos,
):
    arte = _anexo(demand_rascunho_rn)
    solicitacao_id = _criar(auth_client_solicitante, demand_rascunho_rn, {"arte": arte.pk}).data["id"]

    resp = auth_client_solicitante.get(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/documentos/")

    assert resp.status_code == 200
    assert {(d["id"], d["solicitacao"], d["campo"]) for d in resp.data} == {(arte.pk, solicitacao_id, "arte")}
