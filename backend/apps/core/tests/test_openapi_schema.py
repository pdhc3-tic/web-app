"""Gate do schema OpenAPI versionado em `backend/schema.yml`, de onde o
frontend gera os tipos da API."""

from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command
from drf_spectacular.drainage import GENERATOR_STATS

from apps.sgp.services.ufpa_export import FILTROS_ACEITOS

SCHEMA_VERSIONADO = Path(settings.BASE_DIR) / "schema.yml"
REGENERAR = "rode `python manage.py spectacular --file schema.yml` no backend e commite o schema.yml"

# Débito conhecido. Qualquer warning novo fora daqui quebra o teste.
FONTES_COM_DEBITO: tuple[str, ...] = ()
GLOBAIS_COM_DEBITO: tuple[str, ...] = ()
# Rotas do SGD dispensadas do gate de corpo de resposta. Vazia desde a #358.
ROTAS_DO_SGD_FORA_DO_GATE: tuple[str, ...] = ()


@pytest.fixture(scope="module")
def geracao(tmp_path_factory):
    arquivo = tmp_path_factory.mktemp("openapi") / "schema.yml"
    GENERATOR_STATS.reset()
    with GENERATOR_STATS.silence():
        call_command("spectacular", file=str(arquivo), validate=True)
    avisos = [*GENERATOR_STATS._warn_cache, *GENERATOR_STATS._error_cache]
    GENERATOR_STATS.reset()
    return arquivo.read_bytes(), avisos


@pytest.fixture(scope="module")
def schema(geracao):
    return yaml.safe_load(geracao[0])


def _componente(schema, nome):
    return schema["components"]["schemas"][nome]


def _resolver(schema, no):
    if "allOf" in no and len(no["allOf"]) == 1:
        no = no["allOf"][0]
    if "$ref" in no:
        return _componente(schema, no["$ref"].rsplit("/", 1)[-1])
    return no


def _ref(no):
    if "allOf" in no and len(no["allOf"]) == 1:
        no = no["allOf"][0]
    return no.get("$ref", "").rsplit("/", 1)[-1]


def _resposta(schema, rota, metodo="get", codigo="200"):
    conteudo = schema["paths"][rota][metodo]["responses"][codigo]["content"]
    return conteudo["application/json"]["schema"]


def test_schema_versionado_e_o_mesmo_gerado_pelo_codigo(geracao):
    gerado, _ = geracao
    assert SCHEMA_VERSIONADO.exists(), f"schema.yml ausente: {REGENERAR}."
    assert SCHEMA_VERSIONADO.read_bytes() == gerado, f"schema.yml desatualizado: {REGENERAR}."


def test_o_schema_e_gerado_sem_warnings(geracao):
    _, avisos = geracao

    def tem_debito(aviso):
        origem = aviso.split(": ", 1)[0]
        if any(fonte in origem for fonte in FONTES_COM_DEBITO):
            return True
        sem_origem = aviso.startswith(("Warning", "Error"))
        return sem_origem and any(marca in aviso for marca in GLOBAIS_COM_DEBITO)

    novos = sorted(aviso for aviso in avisos if not tem_debito(aviso))
    assert novos == [], "\n".join(novos)


def test_municipio_aninhado_exige_o_estado(schema):
    municipio = _componente(schema, "MunicipioNested")
    assert "estado" in municipio["required"]
    assert _ref(municipio["properties"]["estado"]) == "EstadoNested"
    assert {"id", "sigla", "nome"} <= set(_componente(schema, "EstadoNested")["properties"])

    for componente in ("UFPAList", "UFPADetailResposta", "ActivityDetailResposta"):
        propriedades = _componente(schema, componente)["properties"]
        assert _ref(propriedades["municipio"]) == "MunicipioNested", componente


def test_detalhe_de_ufpa_le_objetos_aninhados_e_escreve_pks(schema):
    resposta = _componente(schema, "UFPADetailResposta")["properties"]
    escrita = _componente(schema, "UFPADetailRequest")["properties"]

    assert _ref(_resposta(schema, "/api/v1/sgp/ufpas/{id}/")) == "UFPADetailResposta"
    assert _ref(_resposta(schema, "/api/v1/sgp/ufpas/", "post", "201")) == "UFPADetailResposta"
    for campo in ("projeto", "municipio"):
        assert escrita[campo]["type"] == "integer"
        assert "type" not in resposta[campo]
    assert {"nome", "cpf"} <= set(escrita)
    assert not {"nome", "cpf"} & set(resposta)
    assert "PatchedUFPADetailRequest" in schema["components"]["schemas"]


def test_detalhe_de_atividade_le_objetos_aninhados(schema):
    resposta = _componente(schema, "ActivityDetailResposta")["properties"]

    assert _ref(_resposta(schema, "/api/v1/sgp/atividades/{id}/")) == "ActivityDetailResposta"
    assert _ref(resposta["acao"]) == "AcaoDaAtividade"
    assert _ref(resposta["tecnico_responsavel"]) == "UsuarioRefComEmail"
    assert _ref(resposta["ufpas_participantes"]["items"]) == "UFPAList"
    assert _componente(schema, "ActivityDetailRequest")["properties"]["acao"]["type"] == "integer"


def test_campos_calculados_saem_com_o_tipo_real(schema):
    ufpa = _componente(schema, "UFPADetailResposta")["properties"]
    assert ufpa["membros"]["type"] == "array"
    assert _ref(ufpa["membros"]["items"]) == "MembroList"

    idade = _componente(schema, "MembroList")["properties"]["idade"]
    assert idade["type"] == "integer"
    assert idade["nullable"] is True

    assert _componente(schema, "ActivityList")["properties"]["atrasada"]["type"] == "boolean"
    transicoes = _componente(schema, "ActivityDetailResposta")["properties"]["transicoes_permitidas"]
    assert _ref(transicoes["items"]) == "StatusAtividadeEnum"

    assert _componente(schema, "BudgetPool")["properties"]["saldo_disponivel"]["type"] == "number"
    perfis = _componente(schema, "UserDetail")["properties"]["perfis"]
    assert _ref(perfis["items"]) == "PerfilDoUsuario"


def test_campos_sensiveis_aparecem_como_opcionais(schema):
    for componente, campos in (
        ("TitularNested", ("cor_raca", "cor_raca_display")),
        ("MembroDetail", ("saude", "cor_raca", "cor_raca_display")),
    ):
        definicao = _componente(schema, componente)
        for campo in campos:
            assert campo in definicao["properties"], (componente, campo)
            assert campo not in definicao.get("required", []), (componente, campo)


def test_exportacao_de_ufpa_documenta_os_mesmos_filtros_que_aceita(schema):
    parametros = schema["paths"]["/api/v1/sgp/ufpas/exportar/"]["get"]["parameters"]
    assert {p["name"] for p in parametros if p["in"] == "query"} == set(FILTROS_ACEITOS) | {"formato"}


@pytest.mark.parametrize(
    ("rota", "metodo"),
    [
        ("/api/v1/sgp/atividades/{id}/fotos/", "get"),
        ("/api/v1/sgp/atividades/{id}/documentos/", "get"),
        ("/api/v1/sgp/atividades/{id}/fotos/reordenar/", "patch"),
        ("/api/v1/sgp/metas/{id}/orcamento/", "get"),
        ("/api/v1/sgd/demandas/{id}/solicitacoes/", "get"),
        ("/api/v1/sgd/demandas/{id}/documentos/", "get"),
    ],
)
def test_listas_sem_paginacao_saem_como_array(schema, rota, metodo):
    operacao = schema["paths"][rota][metodo]
    assert _resposta(schema, rota, metodo)["type"] == "array"
    assert not [p for p in operacao.get("parameters", []) if p["in"] == "query"]


def test_historico_da_ufpa_usa_a_propria_paginacao(schema):
    rota = "/api/v1/sgp/ufpas/{id}/historico/"
    parametros = {p["name"] for p in schema["paths"][rota]["get"]["parameters"] if p["in"] == "query"}
    assert {"page", "page_size", "incluir_membros", "campo"} <= parametros
    assert not {"limit", "offset", "municipio", "ordering"} & parametros
    assert _ref(_resposta(schema, rota)) == "PaginatedHistoricoEntryList"


def test_enums_homonimos_tem_nome_fixo(schema):
    nomes = set(schema["components"]["schemas"])
    assert {
        "StatusAtividadeEnum", "TipoProducaoEnum", "FormatoExportacaoEnum",
        "TipoDocumentoUFPAEnum", "TipoDocumentoAtividadeEnum",
        "DemandStatusEnum", "TipoDocumentoDemandaEnum", "StatusPedidoRecursoExtraEnum",
        "TipoAtividadeEnum", "DecisaoEnum", "DecisaoRecursoExtraEnum",
    } <= nomes
    assert not [nome for nome in nomes if nome.endswith("Enum") and any(c.isdigit() for c in nome)]


def test_rotas_do_sca_descrevem_a_resposta(schema):
    sem_corpo = [
        f"{metodo.upper()} {rota}"
        for rota, operacoes in schema["paths"].items() if rota.startswith("/api/v1/sca/")
        for metodo, operacao in operacoes.items()
        if "content" not in operacao["responses"].get("200", {})
    ]
    assert sem_corpo == []


def test_pull_do_sca_traz_cada_entidade_com_o_envelope(schema):
    resposta = _resolver(schema, _resposta(schema, "/api/v1/sca/sync/pull/"))

    assert set(resposta["properties"]) == {"ufpas", "members", "activities", "saldos", "server_time"}
    for grupo in ("ufpas", "members", "activities"):
        entidade = _resolver(schema, resposta["properties"][grupo]["items"])
        assert {"id", "uuid_local", "atualizado_em"} <= set(entidade["required"])


def test_conflito_do_sca_le_o_tecnico_e_o_registro_atual_com_o_tipo_real(schema):
    conflito = _componente(schema, "ConflictLogDetail")["properties"]

    assert _ref(conflito["tecnico"]) == "UsuarioRefComEmail"
    assert conflito["registro_atual"]["nullable"] is True
    assert {_ref(opcao) for opcao in _resolver(schema, conflito["registro_atual"])["oneOf"]} == {
        "UFPADetailResposta", "MembroDetail", "ActivityDetailResposta",
    }


def test_resolver_conflito_descreve_a_decisao_e_o_conflito_ja_resolvido(schema):
    operacao = schema["paths"]["/api/v1/sca/conflicts/{id}/resolver/"]["post"]

    assert _ref(operacao["requestBody"]["content"]["application/json"]["schema"]) == "ConflictResolveRequest"
    assert _ref(operacao["responses"]["409"]["content"]["application/json"]["schema"]) == "ScaErro"


def test_lista_de_dispositivos_traz_o_limiar_de_alerta(schema):
    pagina = _resolver(schema, _resposta(schema, "/api/v1/sca/devices/"))

    assert pagina["properties"]["limiar_alerta_dias"]["type"] == "integer"
    assert "limiar_alerta_dias" in pagina["required"]


def test_pull_do_sca_descreve_as_datas_da_atividade_e_o_membro_sem_ativo(schema):
    atividade = _componente(schema, "SyncPullActivity")["properties"]

    assert atividade["data_inicio"]["format"] == "date-time"
    assert atividade["data_fim"]["format"] == "date-time"
    assert "ativo" not in _componente(schema, "SyncPullMember")["properties"]


def _resposta_400(schema, rota):
    return schema["paths"][rota]["post"]["responses"]["400"]["content"]["application/json"]["schema"]


def test_400_do_push_cobre_o_erro_proprio_e_o_de_campo_aninhado(schema):
    erro_proprio, erro_de_campo = _resposta_400(schema, "/api/v1/sca/sync/push/")["oneOf"]

    assert _ref(erro_proprio) == "ScaErro"
    assert erro_de_campo == {"type": "object", "additionalProperties": {}}


@pytest.mark.parametrize("rota", ["/api/v1/sca/conflicts/{id}/resolver/", "/api/v1/sca/auth/refresh/"])
def test_400_das_rotas_sem_erro_proprio_e_so_o_de_campo(schema, rota):
    assert _resposta_400(schema, rota) == {"type": "object", "additionalProperties": {}}


def test_schema_so_descreve_ufpa(geracao):
    conteudo, _ = geracao

    assert b"upf" not in conteudo.lower()


def test_rotas_antigas_de_ufpa_ficam_fora_do_schema_e_a_canonica_entra(schema):
    assert not [rota for rota in schema["paths"] if "upf" in rota]
    assert "/api/v1/sgp/ufpas/" in schema["paths"]


def test_rotas_do_sgd_descrevem_a_resposta(schema):
    sem_corpo = [
        f"{metodo.upper()} {rota}"
        for rota, operacoes in schema["paths"].items()
        if rota.startswith("/api/v1/sgd/") and rota not in ROTAS_DO_SGD_FORA_DO_GATE
        for metodo, operacao in operacoes.items() if metodo != "delete"
        if not any("content" in operacao["responses"].get(codigo, {}) for codigo in ("200", "201", "202"))
    ]
    assert sem_corpo == []


def test_detalhe_da_demanda_traz_os_campos_calculados_com_o_tipo_real(schema):
    rota = "/api/v1/sgd/demandas/{id}/"
    assert _ref(_resposta(schema, rota)) == "Demand"
    assert _ref(_resposta(schema, rota, "patch")) == "Demand"
    assert _ref(_resposta(schema, "/api/v1/sgd/demandas/", "post", "201")) == "Demand"

    demanda = _componente(schema, "Demand")["properties"]
    assert _ref(demanda["contexto"]) == "DemandContexto"
    assert _ref(demanda["status"]) == "DemandStatusEnum"
    assert demanda["atividade_fora_do_territorio"]["type"] == "boolean"
    solicitacao = _componente(schema, "DemandRequest")["properties"]
    assert solicitacao["alerta_rubrica_fora_do_previsto"]["type"] == "boolean"


def test_submissao_documenta_o_contrato_de_saldo_insuficiente(schema):
    for rota in ("/api/v1/sgd/demandas/{id}/submeter/", "/api/v1/sgd/demandas/{id}/autorizar/"):
        assert _ref(_resposta(schema, rota, "post")) == "Demand"
        assert _ref(_resposta(schema, rota, "post", "400")) == "SaldoInsuficiente", rota

    erro = _componente(schema, "SaldoInsuficiente")["properties"]
    assert {"code", "trava", "rubrica", "disponivel", "solicitado", "acao_sugerida", "valor_faltante"} <= set(erro)
    assert erro["valor_faltante"]["nullable"] is True
    assert _ref(erro["solicitacoes_bloqueadas"]["additionalProperties"]) == "BloqueioDeSaldo"


def test_preview_da_decisao_le_a_query_e_descreve_o_impacto(schema):
    rota = "/api/v1/sgd/demandas/{id}/preview-decisao/"
    parametros = {p["name"] for p in schema["paths"][rota]["get"]["parameters"] if p["in"] == "query"}
    assert parametros == {"demand_request_id", "valor", "origem_allocation"}

    assert _ref(_resposta(schema, rota)) == "PreviewDecisaoResposta"
    impacto = _componente(schema, "PreviewDecisaoResposta")["properties"]
    assert _ref(impacto["individual"]) == _ref(impacto["territorial"]) == "ImpactoNaTrava"
    assert _componente(schema, "ImpactoNaTrava")["properties"]["saldo_apos"]["type"] == "number"


def test_listagens_paginadas_do_sgd_usam_o_proprio_envelope(schema):
    for rota, componente in (
        ("/api/v1/sgd/remanejamentos/", "PaginatedBudgetIncreaseRequestList"),
        ("/api/v1/sgd/remanejamentos/transferencias/", "PaginatedBudgetTransferList"),
        ("/api/v1/sgd/demandas/{id}/auditoria/", "PaginatedDemandAuditEntryList"),
    ):
        assert _ref(_resposta(schema, rota)) == componente, rota
        parametros = {p["name"] for p in schema["paths"][rota]["get"]["parameters"] if p["in"] == "query"}
        assert {"limit", "offset"} <= parametros, rota
        assert "periodo_inicio" not in parametros, rota


def test_paineis_do_sgd_documentam_os_filtros_da_listagem(schema):
    filtros_da_listagem = {
        p["name"] for p in schema["paths"]["/api/v1/sgd/demandas/"]["get"]["parameters"] if p["in"] == "query"
    } - {"limit", "offset", "ordering"}
    for rota in ("/api/v1/sgd/painel/rubricas/", "/api/v1/sgd/relatorios/custo-por-atividade/"):
        parametros = {p["name"] for p in schema["paths"][rota]["get"]["parameters"] if p["in"] == "query"}
        assert filtros_da_listagem <= parametros, rota
        assert _resposta(schema, rota)["type"] == "array"
