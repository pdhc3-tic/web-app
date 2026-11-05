"""Catálogo de tipos de solicitação: CRUD, validação por schema e estratégias."""
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.models.audit_log import AuditLog
from apps.sgd import constants
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models import DemandRequest, TipoSolicitacao
from apps.sgd.services import demand as demand_service
from apps.sgd.services.demand_request import validar_campos_json
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory, TipoSolicitacaoFactory
from apps.sgp.tests.factories import BudgetRubricaFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/config/tipos-solicitacao/"
SCHEMA_HOSPEDAGEM = {
    "type": "object",
    "required": ["hotel"],
    "properties": {"hotel": {"title": "Hotel", "type": "string"}, "noites": {"type": "integer", "minimum": 1}},
}
CAMPOS_GRAFICO = {
    "tipo_material": "banner", "quantidade": 1,
    "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
}


def _url_solicitacoes(demand):
    return f"/api/v1/sgd/demandas/{demand.pk}/solicitacoes/"


# ---------- Tipo novo ----------

def test_super_admin_cria_hospedagem_e_adt_solicita(
    auth_client_super_admin, solicitante_rn, demand_rascunho_rn, rubrica_diarias,
):
    resp = auth_client_super_admin.post(URL, {
        "slug": "hospedagem", "nome": "Hospedagem", "rubrica": rubrica_diarias.pk, "schema_campos": SCHEMA_HOSPEDAGEM,
    }, format="json")
    assert resp.status_code == 201
    assert AuditLog.objects.filter(acao="tipo_solicitacao.criado", entidade_id=str(resp.data["id"])).exists()

    auth_client_super_admin.force_authenticate(user=solicitante_rn)
    resp = auth_client_super_admin.post(_url_solicitacoes(demand_rascunho_rn), {
        "tipo": "hospedagem", "campos_json": {"hotel": "Hotel Central", "noites": 2}, "valor_estimado": "300.00",
    }, format="json")

    assert resp.status_code == 201, resp.data
    assert resp.data["tipo"] == "hospedagem"
    assert resp.data["tipo_display"] == "Hospedagem"
    assert resp.data["rubrica"] == rubrica_diarias.pk


def test_tipo_novo_sem_validador_usa_so_a_validacao_por_schema(activity_rn):
    TipoSolicitacaoFactory(slug="hospedagem", schema_campos=SCHEMA_HOSPEDAGEM)

    validado = validar_campos_json("hospedagem", {"hotel": "Hotel Central", "extra": "x"}, activity_rn)

    assert validado.campos_json == {"hotel": "Hotel Central", "extra": "x"}
    assert validado.beneficiario_cpf is None
    assert validado.valor_estimado_auto is None
    with pytest.raises(RegraDeNegocio) as ausente:
        validar_campos_json("hospedagem", {"noites": 2}, activity_rn)
    assert ausente.value.campo == "campos_json"
    with pytest.raises(RegraDeNegocio) as invalido:
        validar_campos_json("hospedagem", {"hotel": "Hotel Central", "noites": 0}, activity_rn)
    assert invalido.value.campo == "noites"


def test_tipo_novo_com_validador_registrado_usa_a_estrategia(demand_rascunho_rn, rubrica_diarias):
    tipo = TipoSolicitacaoFactory(slug="diaria-especial", rubrica=rubrica_diarias, validador="passagem")

    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo=tipo.slug, campos_json={"passageiro_cpf": "52998224725"}, valor_estimado=100,
    )

    assert "passageiro_cpf" not in solicitacao.campos_json
    assert solicitacao.beneficiario_cpf


@pytest.mark.parametrize("schema,campos,campo", [
    ({"$ref": "#/$defs/ausente"}, {}, "tipo"),
    ({"properties": {"proibido": False}}, {"proibido": 1}, "campos_json"),
    ({"properties": {"opcao": {"enum": [1, "a"]}}}, {"opcao": "b"}, "opcao"),
    ({"properties": {"noites": {"type": "integer"}}}, {"noites": ""}, "noites"),
    ({"properties": {"noites": {"type": "integer"}}}, {"noites": None}, "noites"),
    (
        {"properties": {"hospede": {"type": "object", "required": ["nome"]}}},
        {"nome": "Nome na raiz", "hospede": {}}, "hospede.nome",
    ),
])
def test_schema_configuravel_rejeita_campos_sem_erro_interno(
    auth_client_super_admin, demand_rascunho_rn, solicitante_rn, rubrica_diarias, schema, campos, campo,
):
    resposta = auth_client_super_admin.post(URL, {
        "slug": "hospedagem", "nome": "Hospedagem", "rubrica": rubrica_diarias.pk, "schema_campos": schema,
    }, format="json")
    assert resposta.status_code == 201
    auth_client_super_admin.force_authenticate(user=solicitante_rn)

    resposta = auth_client_super_admin.post(_url_solicitacoes(demand_rascunho_rn), {
        "tipo": "hospedagem", "campos_json": campos, "valor_estimado": "100.00",
    }, format="json")

    assert resposta.status_code == 400
    assert resposta.data["code"] == "BUSINESS_RULE"
    assert campo in resposta.data


@pytest.mark.parametrize("validador,campo", [
    ("diaria", "municipio_destino_id"), ("passagem", "passageiro_cpf"),
])
def test_estrategia_exige_seus_campos_mesmo_com_schema_vazio(
    auth_client_solicitante, demand_rascunho_rn, validador, campo,
):
    TipoSolicitacaoFactory(slug="especial", validador=validador, schema_campos={})

    resposta = auth_client_solicitante.post(_url_solicitacoes(demand_rascunho_rn), {
        "tipo": "especial", "campos_json": {}, "valor_estimado": "100.00",
    }, format="json")

    assert resposta.status_code == 400
    assert resposta.data["code"] == "BUSINESS_RULE"
    assert campo in resposta.data


def test_catalogo_no_admin_e_somente_leitura(rf):
    from django.contrib.admin.sites import site

    model_admin = site._registry[TipoSolicitacao]
    request = rf.get("/admin/")

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


# ---------- Leitura e permissão ----------

def test_leitura_para_autenticado_e_filtro_por_ativo(auth_client_solicitante):
    TipoSolicitacaoFactory(slug="antigo", ativo=False, ordem=99)

    tudo = auth_client_solicitante.get(URL)
    ativos = auth_client_solicitante.get(URL, {"ativo": "true"})

    assert tudo.status_code == 200
    assert "antigo" in {t["slug"] for t in tudo.data}
    assert "antigo" not in {t["slug"] for t in ativos.data}
    primeiro = next(t for t in tudo.data if t["slug"] == "diaria")
    assert {"nome", "rubrica", "rubrica_nome", "schema_campos", "validador", "ativo", "ordem"} <= set(primeiro)


def test_sem_autenticacao_recebe_401(api_client):
    assert api_client.get(URL).status_code == 401


@pytest.mark.parametrize("cliente", ["auth_client_ugp", "auth_client_solicitante"])
def test_escrita_e_so_do_super_admin(cliente, request, rubrica_diarias):
    client = request.getfixturevalue(cliente)
    tipo = TipoSolicitacao.objects.get(slug="diaria")

    assert client.post(
        URL, {"slug": "novo", "nome": "Novo", "rubrica": rubrica_diarias.pk}, format="json",
    ).status_code == 403
    assert client.patch(f"{URL}{tipo.pk}/", {"nome": "Outro"}, format="json").status_code == 403
    assert client.delete(f"{URL}{tipo.pk}/").status_code == 403


# ---------- Regras do cadastro ----------

@pytest.mark.parametrize("campo,valor", [
    ("validador", "nao_registrado"),
    ("schema_campos", {"type": "tipo-que-nao-existe"}),
    ("schema_campos", ["nao", "e", "objeto"]),
])
def test_cadastro_invalido_retorna_400_no_campo(auth_client_super_admin, rubrica_diarias, campo, valor):
    resp = auth_client_super_admin.post(URL, {
        "slug": "novo", "nome": "Novo", "rubrica": rubrica_diarias.pk, campo: valor,
    }, format="json")

    assert resp.status_code == 400
    assert campo in resp.data


def test_rubrica_inativa_retorna_400(auth_client_super_admin):
    rubrica = BudgetRubricaFactory(slug="inativa", ativo=False)

    resp = auth_client_super_admin.post(URL, {"slug": "novo", "nome": "Novo", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "rubrica" in resp.data


def test_slug_nao_pode_ser_alterado(auth_client_super_admin):
    tipo = TipoSolicitacao.objects.get(slug="diaria")

    resp = auth_client_super_admin.patch(f"{URL}{tipo.pk}/", {"slug": "outro"}, format="json")

    assert resp.status_code == 400
    assert "slug" in resp.data


def test_remover_tipo_em_uso_retorna_400_e_mantem_o_tipo(auth_client_super_admin, demand_rascunho_rn):
    tipo = TipoSolicitacao.objects.get(slug="grafico")
    DemandRequestFactory(demanda=demand_rascunho_rn, tipo="grafico")

    resp = auth_client_super_admin.delete(f"{URL}{tipo.pk}/")

    assert resp.status_code == 400
    assert TipoSolicitacao.objects.filter(pk=tipo.pk).exists()


def test_remover_tipo_sem_solicitacoes_apaga_e_audita(auth_client_super_admin):
    tipo = TipoSolicitacaoFactory(slug="sem-uso")

    resp = auth_client_super_admin.delete(f"{URL}{tipo.pk}/")

    assert resp.status_code == 204
    assert not TipoSolicitacao.objects.filter(pk=tipo.pk).exists()
    assert AuditLog.objects.filter(acao="tipo_solicitacao.removido", entidade_id=str(tipo.pk)).exists()


# ---------- Desativação ----------

def test_desativar_nao_afeta_as_solicitacoes_existentes(auth_client_super_admin, demand_rascunho_rn):
    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )
    rubrica = solicitacao.rubrica_id
    tipo = TipoSolicitacao.objects.get(slug="grafico")

    resp = auth_client_super_admin.patch(f"{URL}{tipo.pk}/", {"ativo": False}, format="json")
    assert resp.status_code == 200

    solicitacao.refresh_from_db()
    assert (solicitacao.tipo_id, solicitacao.rubrica_id) == ("grafico", rubrica)
    atualizada = demand_service.atualizar_solicitacao(
        solicitacao, usuario=demand_rascunho_rn.solicitante, campos_json={**CAMPOS_GRAFICO, "quantidade": 3},
    )
    assert atualizada.campos_json["quantidade"] == 3
    with pytest.raises(RegraDeNegocio):
        demand_service.adicionar_solicitacao(
            demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
        )


# ---------- Equivalência dos seis tipos semeados ----------

@pytest.mark.parametrize("slug,campo,constante", [
    ("diaria", "beneficiario_vinculo", constants.Vinculo),
    ("diaria", "meio_transporte", constants.MeioTransporte),
    ("passagem", "classe", constants.Classe),
    ("passagem", "urgencia", constants.Urgencia),
    ("veiculo", "tipo_veiculo", constants.TipoVeiculo),
    ("grafico", "tipo_material", constants.TipoMaterial),
    ("alimentacao", "tipo_refeicao", constants.TipoRefeicao),
    ("equipamento", "urgencia", constants.Urgencia),
])
def test_enumeracoes_do_schema_acompanham_as_constantes(slug, campo, constante):
    schema = TipoSolicitacao.objects.get(slug=slug).schema_campos

    assert set(schema["properties"][campo]["enum"]) == set(constante.values)


@pytest.mark.parametrize("quantidade,valido", [(5, True), ("5", True), (0, False), ("0", False), (-1, False),
                                               (1.5, False), ("abc", False), (True, False)])
def test_inteiro_positivo(activity_rn, quantidade, valido):
    campos = {**CAMPOS_GRAFICO, "quantidade": quantidade}

    if valido:
        assert validar_campos_json("grafico", campos, activity_rn).campos_json["quantidade"] == quantidade
        return
    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("grafico", campos, activity_rn)
    assert excinfo.value.campo == "quantidade"


def test_vazio_conta_como_ausente_e_lista_todos_os_campos(activity_rn):
    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("grafico", {"tipo_material": "", "quantidade": None}, activity_rn)

    assert excinfo.value.campo == "campos_json"
    assert "tipo_material, quantidade, especificacoes_tecnicas, prazo_entrega" in excinfo.value.mensagem


def test_enumeracao_invalida_aponta_o_campo_e_as_opcoes(activity_rn):
    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("grafico", {**CAMPOS_GRAFICO, "tipo_material": "faixa"}, activity_rn)

    assert excinfo.value.campo == "tipo_material"
    assert "banner" in excinfo.value.mensagem


def test_prazo_com_data_invalida_aponta_o_campo(activity_rn):
    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("grafico", {**CAMPOS_GRAFICO, "prazo_entrega": "amanhã"}, activity_rn)

    assert excinfo.value.campo == "prazo_entrega"


@pytest.mark.parametrize("campos,campo", [
    ({"ida_e_volta": True}, "data_hora_volta"),
    ({"classe": "executiva"}, "justificativa_executiva"),
])
def test_regras_condicionais_da_passagem_apontam_o_campo(activity_rn, campos, campo):
    base = {
        "passageiro_nome": "Fulano", "passageiro_cpf": "52998224725", "passageiro_data_nascimento": "1990-01-01",
        "aeroporto_origem": "NAT", "aeroporto_destino": "GRU", "data_hora_ida": "2026-06-01T08:00:00Z",
        "ida_e_volta": False, "bagagem_despachada": True, "classe": "economica", "urgencia": "normal",
    }

    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("passagem", {**base, **campos}, activity_rn)

    assert excinfo.value.campo == campo
    assert "Obrigatório quando" in excinfo.value.mensagem


def test_cotacoes_seguem_a_estrategia_na_submissao(demand_rascunho_rn, solicitante_rn):
    tipo = TipoSolicitacaoFactory(slug="equipamento-especial", validador="equipamento")
    DemandRequestFactory(demanda=demand_rascunho_rn, tipo=tipo)

    with pytest.raises(RegraDeNegocio) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    assert excinfo.value.campo == "documentos"


def test_cpf_volta_na_leitura_pela_chave_da_estrategia(auth_client_solicitante, demand_rascunho_rn):
    tipo = TipoSolicitacaoFactory(slug="passagem-especial", validador="passagem")
    DemandRequestFactory(
        demanda=demand_rascunho_rn, tipo=tipo, campos_json={"passageiro_nome": "Fulano"},
        beneficiario_cpf="52998224725",
    )

    resp = auth_client_solicitante.get(_url_solicitacoes(demand_rascunho_rn))

    assert resp.data[0]["campos_json"]["passageiro_cpf"] == "52998224725"


# ---------- Filtro ----------

def test_filtro_tipo_aceita_slug_do_catalogo_e_recusa_o_inexistente(auth_client_super_admin, activity_rn):
    com_o_tipo = DemandFactory(activity=activity_rn)
    DemandRequestFactory(demanda=com_o_tipo, tipo="grafico")
    DemandFactory(activity=activity_rn)

    ok = auth_client_super_admin.get("/api/v1/sgd/demandas/", {"tipo": "grafico"})
    invalido = auth_client_super_admin.get("/api/v1/sgd/demandas/", {"tipo": "inexistente"})

    assert ok.status_code == 200
    assert [d["id"] for d in ok.json()["results"]] == [com_o_tipo.pk]
    assert invalido.status_code == 400


# ---------- Migrations ----------

ANTES = [("sgd", "0019_remover_demandindividuallimit")]
DEPOIS = [("sgd", "0021_tipo_vira_fk_do_catalogo")]


def _migrar(alvo):
    MigrationExecutor(connection).migrate(alvo)
    return MigrationExecutor(connection).loader.project_state(alvo).apps


@pytest.fixture
def banco_antes_da_migracao():
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_migracao_converte_mapeamentos_e_preserva_o_slug_das_solicitacoes(banco_antes_da_migracao, activity_rn):
    demand = DemandFactory(activity=activity_rn)
    solicitacao = DemandRequestFactory(demanda=demand, tipo="grafico")

    apps_antes = _migrar(ANTES)
    Mapeamento = apps_antes.get_model("sgd", "DemandTypeRubricaMapping")
    Rubrica = apps_antes.get_model("sgp", "BudgetRubrica")
    Config = apps_antes.get_model("core", "SystemConfig")
    assert apps_antes.get_model("sgd", "DemandRequest").objects.get(pk=solicitacao.pk).tipo == "grafico"
    rubrica = Rubrica.objects.create(nome="Da migração", slug="da-migracao")
    Mapeamento.objects.all().delete()
    Mapeamento.objects.create(tipo="diaria", rubrica=rubrica, ativo=True)
    Mapeamento.objects.create(tipo="diaria", rubrica=Rubrica.objects.get(slug="material-grafico"), ativo=False)
    Config.objects.update_or_create(chave="sgd_mapeamento_tipo_rubrica", defaults={"valor": "{}", "tipo": "json"})

    apps_depois = _migrar(DEPOIS)

    Tipo = apps_depois.get_model("sgd", "TipoSolicitacao")
    assert Tipo.objects.count() == 6
    diaria = Tipo.objects.get(slug="diaria")
    assert (diaria.rubrica_id, diaria.ativo, diaria.validador) == (rubrica.pk, True, "diaria")
    sem_mapeamento = Tipo.objects.get(slug="veiculo")
    assert sem_mapeamento.ativo is False
    assert sem_mapeamento.rubrica.slug == "locacao-veiculo"
    assert apps_depois.get_model("sgd", "DemandRequest").objects.get(pk=solicitacao.pk).tipo_id == "grafico"
    assert not apps_depois.get_model("core", "SystemConfig").objects.filter(
        chave="sgd_mapeamento_tipo_rubrica",
    ).exists()


def test_semeadura_tem_os_seis_tipos_com_validador_registrado():
    from apps.sgd.services.tipos_solicitacao import validadores_registrados

    semeadura = import_module("apps.sgd.migrations.0020_tipo_solicitacao")

    assert {slug for slug, *_ in semeadura.TIPOS} == set(validadores_registrados())
    assert DemandRequest._meta.get_field("tipo").remote_field.field_name == "slug"
