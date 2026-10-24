"""Gate do schema OpenAPI versionado em `backend/schema.yml`, de onde o
frontend gera os tipos da API."""

from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command
from drf_spectacular.drainage import GENERATOR_STATS

from apps.sgp.services.upf_export import FILTROS_ACEITOS

SCHEMA_VERSIONADO = Path(settings.BASE_DIR) / "schema.yml"
REGENERAR = "rode `python manage.py spectacular --file schema.yml` no backend e commite o schema.yml"

# Débito conhecido, fora do recorte de SGP + core: SGD e SCA ainda geram
# warnings. Qualquer warning novo fora daqui quebra o teste.
FONTES_COM_DEBITO = ("/apps/sgd/", "/apps/sca/")
GLOBAIS_COM_DEBITO = ("v1_sgd_",)


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


def test_sgp_e_core_geram_o_schema_sem_warnings(geracao):
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

    for componente in ("UPFList", "UPFDetailResposta", "ActivityDetailResposta"):
        propriedades = _componente(schema, componente)["properties"]
        assert _ref(propriedades["municipio"]) == "MunicipioNested", componente


def test_detalhe_de_upf_le_objetos_aninhados_e_escreve_pks(schema):
    resposta = _componente(schema, "UPFDetailResposta")["properties"]
    escrita = _componente(schema, "UPFDetailRequest")["properties"]

    assert _ref(_resposta(schema, "/api/v1/upfs/{id}/")) == "UPFDetailResposta"
    assert _ref(_resposta(schema, "/api/v1/upfs/", "post", "201")) == "UPFDetailResposta"
    for campo in ("projeto", "municipio"):
        assert escrita[campo]["type"] == "integer"
        assert "type" not in resposta[campo]
    assert {"nome", "cpf"} <= set(escrita)
    assert not {"nome", "cpf"} & set(resposta)
    assert "PatchedUPFDetailRequest" in schema["components"]["schemas"]


def test_detalhe_de_atividade_le_objetos_aninhados(schema):
    resposta = _componente(schema, "ActivityDetailResposta")["properties"]

    assert _ref(_resposta(schema, "/api/v1/sgp/atividades/{id}/")) == "ActivityDetailResposta"
    assert _ref(resposta["acao"]) == "AcaoDaAtividade"
    assert _ref(resposta["tecnico_responsavel"]) == "UsuarioRefComEmail"
    assert _ref(resposta["upfs_participantes"]["items"]) == "UPFList"
    assert _componente(schema, "ActivityDetailRequest")["properties"]["acao"]["type"] == "integer"


def test_campos_calculados_saem_com_o_tipo_real(schema):
    upf = _componente(schema, "UPFDetailResposta")["properties"]
    assert upf["membros"]["type"] == "array"
    assert _ref(upf["membros"]["items"]) == "MembroList"

    idade = _componente(schema, "MembroList")["properties"]["idade"]
    assert idade["type"] == "integer"
    assert idade["nullable"] is True

    assert _componente(schema, "ActivityList")["properties"]["atrasada"]["type"] == "boolean"
    transicoes = _componente(schema, "ActivityDetailResposta")["properties"]["transicoes_permitidas"]
    assert _ref(transicoes["items"]) == "StatusAtividadeEnum"

    assert _componente(schema, "BudgetAllocation")["properties"]["saldo_disponivel"]["type"] == "number"
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


def test_exportacao_de_upf_documenta_os_mesmos_filtros_que_aceita(schema):
    parametros = schema["paths"]["/api/v1/upfs/exportar/"]["get"]["parameters"]
    assert {p["name"] for p in parametros if p["in"] == "query"} == set(FILTROS_ACEITOS) | {"formato"}


@pytest.mark.parametrize(
    ("rota", "metodo"),
    [
        ("/api/v1/sgp/atividades/{id}/fotos/", "get"),
        ("/api/v1/sgp/atividades/{id}/documentos/", "get"),
        ("/api/v1/sgp/atividades/{id}/fotos/reordenar/", "patch"),
        ("/api/v1/sgp/metas/{id}/orcamento/", "get"),
    ],
)
def test_listas_sem_paginacao_saem_como_array(schema, rota, metodo):
    operacao = schema["paths"][rota][metodo]
    assert _resposta(schema, rota, metodo)["type"] == "array"
    assert not [p for p in operacao.get("parameters", []) if p["in"] == "query"]


def test_historico_da_upf_usa_a_propria_paginacao(schema):
    rota = "/api/v1/upfs/{id}/historico/"
    parametros = {p["name"] for p in schema["paths"][rota]["get"]["parameters"] if p["in"] == "query"}
    assert {"page", "page_size", "incluir_membros", "campo"} <= parametros
    assert not {"limit", "offset", "municipio", "ordering"} & parametros
    assert _ref(_resposta(schema, rota)) == "PaginatedHistoricoEntryList"


def test_enums_homonimos_tem_nome_fixo(schema):
    nomes = set(schema["components"]["schemas"])
    assert {
        "StatusAtividadeEnum", "TipoProducaoEnum", "FormatoExportacaoEnum",
        "TipoDocumentoUPFEnum", "TipoDocumentoAtividadeEnum",
    } <= nomes
