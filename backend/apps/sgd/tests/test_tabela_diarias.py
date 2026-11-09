"""Tabela de diárias nos moldes do serviço público federal (#358): faixa de destino,
vigência, contagem com meia diária, adicional de embarque e manutenção pela FGD."""
from datetime import date
from decimal import Decimal

import pytest

from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import MunicipalityFactory, StateFactory
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models import TabelaDiaria
from apps.sgd.services import diarias as diarias_service
from apps.sgd.services.demand_request import validar_campos_json

pytestmark = pytest.mark.django_db

URL_TABELA = "/api/v1/sgd/config/diarias/tabela/"
URL_FAIXAS = "/api/v1/sgd/config/diarias/faixas/"


def _municipio(nome, uf, codigo_ibge):
    return MunicipalityFactory(nome=nome, state=StateFactory(sigla=uf), codigo_ibge=codigo_ibge)


def _campos(municipio, inicio="2026-11-02", fim="2026-11-04", **extra):
    return {
        "beneficiario_nome": "Fulano", "beneficiario_cpf": "52998224725", "beneficiario_cargo": "Técnico",
        "beneficiario_vinculo": "servidor_ufersa", "municipio_destino_id": municipio.pk,
        "data_inicio": inicio, "data_fim": fim, "meio_transporte": "rodoviario",
        "justificativa": "Visita técnica.", **extra,
    }


# --- Contagem -------------------------------------------------------------------------


@pytest.mark.parametrize(("inicio", "fim", "custeada", "esperado"), [
    (date(2026, 11, 2), date(2026, 11, 2), False, Decimal("0.5")),  # mesmo dia
    (date(2026, 11, 2), date(2026, 11, 3), False, Decimal("1.5")),  # 1 pernoite
    (date(2026, 11, 2), date(2026, 11, 4), False, Decimal("2.5")),  # 2 pernoites
    (date(2026, 11, 2), date(2026, 11, 4), True, Decimal("1.5")),   # 2 pernoites custeados
    (date(2026, 11, 2), date(2026, 11, 2), True, Decimal("0.5")),
])
def test_contagem_padrao_federal(inicio, fim, custeada, esperado):
    assert diarias_service.contar_diarias(inicio, fim, custeada) == esperado


def test_regras_desligadas_contam_inteira(regras_diaria):
    regras_diaria(
        sgd_diaria_regra_meia_no_retorno=False,
        sgd_diaria_regra_meia_sem_pernoite=False,
        sgd_diaria_regra_meia_hospedagem_custeada=False,
    )

    assert diarias_service.contar_diarias(date(2026, 11, 2), date(2026, 11, 2)) == Decimal("1.0")
    assert diarias_service.contar_diarias(date(2026, 11, 2), date(2026, 11, 4), True) == Decimal("3.0")


def test_sem_regra_de_pernoite_conta_dias_corridos(regras_diaria):
    regras_diaria(sgd_diaria_regra_inteira_por_pernoite=False)

    assert diarias_service.contar_diarias(date(2026, 11, 2), date(2026, 11, 4)) == Decimal("3.0")


# --- Faixa de destino -----------------------------------------------------------------


# Anexo I vigente (Decreto 11.872/2023): Recife, que tinha faixa própria no anexo de
# 2009, está entre as demais capitais; São Paulo passou à primeira faixa.
@pytest.mark.parametrize(("nome", "uf", "codigo", "ordem"), [
    ("Manaus", "AM", "1302603", 1),
    ("São Paulo", "SP", "3550308", 1),
    ("Recife", "PE", "2611606", 2),
    ("Palmas", "TO", "1721000", 2),
    ("Mossoró", "RN", "2408003", 3),
])
def test_municipio_cai_na_sua_faixa(faixas_diaria, nome, uf, codigo, ordem):
    assert diarias_service.resolver_faixa(_municipio(nome, uf, codigo)) == faixas_diaria[ordem]


def test_enquadramento_explicito_prevalece_sobre_o_padrao(faixas_diaria):
    natal = _municipio("Natal", "RN", "2408102")
    faixas_diaria[1].enquadramentos.create(codigo_ibge="2408102", nome_referencia="Natal/RN")

    assert diarias_service.resolver_faixa(natal) == faixas_diaria[1]


# --- Vigência -------------------------------------------------------------------------


def test_limites_de_vigencia_sao_inclusivos(faixas_diaria, tabela_diaria):
    faixa = faixas_diaria[3]
    [linha] = tabela_diaria("300", faixas=[faixa], inicio=date(2026, 1, 1), fim=date(2026, 12, 31))

    assert diarias_service.valor_vigente(faixa, date(2026, 1, 1)) == linha
    assert diarias_service.valor_vigente(faixa, date(2026, 12, 31)) == linha
    with pytest.raises(RegraDeNegocio) as excinfo:
        diarias_service.valor_vigente(faixa, date(2027, 1, 1))
    assert "Demais localidades" in str(excinfo.value)
    assert "01/01/2027" in str(excinfo.value)


def test_valor_editado_vale_a_partir_da_nova_vigencia(faixas_diaria, tabela_diaria, usuario_fgd):
    faixa = faixas_diaria[3]
    [atual] = tabela_diaria("300", faixas=[faixa], inicio=date(2026, 1, 1))

    nova = diarias_service.registrar_nova_vigencia(
        atual=atual, valor=Decimal("350"), inicio=date(2026, 7, 1), origem="fgd", user=usuario_fgd,
    )

    atual.refresh_from_db()
    assert atual.valor == Decimal("300")
    assert atual.vigencia_fim == date(2026, 6, 30)
    assert (nova.vigencia_inicio, nova.vigencia_fim, nova.valor) == (date(2026, 7, 1), None, Decimal("350"))
    assert diarias_service.valor_vigente(faixa, date(2026, 6, 30)) == atual
    assert diarias_service.valor_vigente(faixa, date(2026, 7, 1)) == nova


def test_alterar_a_tabela_nao_muda_solicitacao_gravada(
    activity_rn, municipio_rn, faixas_diaria, tabela_diaria, usuario_fgd,
):
    [atual] = tabela_diaria("300", faixas=[faixas_diaria[3]], inicio=date(2026, 1, 1))
    validado = validar_campos_json("diaria", _campos(municipio_rn), activity_rn)
    congelado = dict(validado.campos_json)

    diarias_service.registrar_nova_vigencia(
        atual=atual, valor=Decimal("500"), inicio=date(2026, 11, 1), origem="fgd", user=usuario_fgd,
    )

    assert congelado["tabela_diaria_id"] == atual.pk
    assert congelado["valor_por_diaria"] == "300.00"
    assert congelado["numero_diarias"] == "2.5"
    assert congelado["faixa_destino"] == {"id": faixas_diaria[3].pk, "nome": "Demais localidades"}
    assert validado.valor_estimado_auto == Decimal("750.00")


def test_adicional_de_embarque_entra_no_total(activity_rn, municipio_rn, tabela_diaria, regras_diaria):
    tabela_diaria("300")
    regras_diaria(sgd_diaria_adicional_embarque_ativo=True, sgd_diaria_adicional_embarque_valor="95.00")

    validado = validar_campos_json("diaria", _campos(municipio_rn, hospedagem_custeada=True), activity_rn)

    assert validado.campos_json["hospedagem_custeada"] is True
    assert validado.campos_json["adicional_embarque"] == "95.00"
    assert validado.valor_estimado_auto == Decimal("545.00")  # 1,5 × 300 + 95


# --- API ------------------------------------------------------------------------------


def test_faixas_semeadas_sao_listadas(auth_client_solicitante, faixas_diaria):
    resposta = auth_client_solicitante.get(URL_FAIXAS)

    assert resposta.status_code == 200
    assert [f["nome"] for f in resposta.json()][:3] == [
        "Brasília, Manaus, Rio de Janeiro e São Paulo",
        "Demais capitais",
        "Demais localidades",
    ]


@pytest.mark.parametrize("cliente", ["auth_client_fgd", "auth_client_super_admin"])
def test_fgd_e_super_admin_cadastram_valor(request, cliente, faixas_diaria):
    resposta = request.getfixturevalue(cliente).post(URL_TABELA, {
        "faixa_destino": faixas_diaria[1].pk, "vigencia_inicio": "2026-01-01", "valor": "425.00",
        "origem": "federal",
    }, format="json")

    assert resposta.status_code == 201, resposta.data
    assert AuditLog.objects.filter(acao="tabela_diaria.criado", entidade_id=str(resposta.data["id"])).exists()


def test_adt_nao_altera_a_tabela(auth_client_solicitante, faixas_diaria):
    resposta = auth_client_solicitante.post(URL_TABELA, {
        "faixa_destino": faixas_diaria[1].pk, "vigencia_inicio": "2026-01-01", "valor": "425.00",
        "origem": "federal",
    }, format="json")

    assert resposta.status_code == 403


def test_vigencia_sobreposta_e_recusada(auth_client_fgd, faixas_diaria, tabela_diaria):
    tabela_diaria("300", faixas=[faixas_diaria[1]], inicio=date(2026, 1, 1))

    resposta = auth_client_fgd.post(URL_TABELA, {
        "faixa_destino": faixas_diaria[1].pk, "vigencia_inicio": "2026-06-01", "valor": "425.00",
        "origem": "federal",
    }, format="json")

    assert resposta.status_code == 400
    assert "vigencia_inicio" in resposta.data


def test_editar_cria_nova_vigencia_e_audita(auth_client_fgd, faixas_diaria, tabela_diaria):
    [atual] = tabela_diaria("300", faixas=[faixas_diaria[1]], inicio=date(2026, 1, 1))

    resposta = auth_client_fgd.patch(f"{URL_TABELA}{atual.pk}/", {
        "valor": "425.00", "vigencia_inicio": "2026-07-01", "origem": "federal",
    }, format="json")

    assert resposta.status_code == 201, resposta.data
    assert resposta.data["id"] != atual.pk
    assert TabelaDiaria.objects.filter(faixa_destino=faixas_diaria[1]).count() == 2
    log = AuditLog.objects.get(acao="tabela_diaria.nova_vigencia")
    assert log.valores_anteriores["valor"] == "300.00"
    assert log.valores_novos["valor"] == "425.00"


def test_nova_vigencia_nao_pode_comecar_antes_da_editada(auth_client_fgd, faixas_diaria, tabela_diaria):
    [atual] = tabela_diaria("300", faixas=[faixas_diaria[1]], inicio=date(2026, 1, 1))

    resposta = auth_client_fgd.patch(f"{URL_TABELA}{atual.pk}/", {
        "valor": "425.00", "vigencia_inicio": "2026-01-01", "origem": "federal",
    }, format="json")

    assert resposta.status_code == 400
    assert TabelaDiaria.objects.get(pk=atual.pk).vigencia_fim is None


# --- Parâmetros do Core ---------------------------------------------------------------

URL_PARAMETROS = "/api/v1/sgd/config/diarias/parametros/"


def test_parametros_seguem_o_padrao_federal(auth_client_solicitante):
    resposta = auth_client_solicitante.get(URL_PARAMETROS)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "regra_inteira_por_pernoite": True,
        "regra_meia_no_retorno": True,
        "regra_meia_sem_pernoite": True,
        "regra_meia_hospedagem_custeada": True,
        "adicional_embarque_ativo": False,
        "adicional_embarque_valor": "95.00",
    }


@pytest.mark.parametrize("cliente", ["auth_client_fgd", "auth_client_super_admin"])
def test_fgd_e_super_admin_alteram_parametros_e_a_contagem_muda(request, cliente):
    from django.core.cache import cache

    # O cache do SystemConfig não é transacional: limpa ao fim para não vazar.
    try:
        resposta = request.getfixturevalue(cliente).patch(URL_PARAMETROS, {
            "regra_meia_no_retorno": False, "adicional_embarque_ativo": True, "adicional_embarque_valor": "100",
        }, format="json")

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["regra_meia_no_retorno"] is False
        assert resposta.data["adicional_embarque_valor"] == "100.00"
        assert diarias_service.contar_diarias(date(2026, 11, 2), date(2026, 11, 4)) == Decimal("3.0")
        assert diarias_service.adicional_embarque() == Decimal("100.00")
        assert AuditLog.objects.filter(acao="system_config.updated").count() == 3
    finally:
        for chave in diarias_service.PARAMETROS.values():
            cache.delete(f"system_config:{chave}")


def test_adt_nao_altera_parametros(auth_client_solicitante):
    resposta = auth_client_solicitante.patch(URL_PARAMETROS, {"regra_meia_no_retorno": False}, format="json")

    assert resposta.status_code == 403


def test_fgd_nao_ganha_acesso_as_demais_configuracoes_do_core(auth_client_fgd):
    resposta = auth_client_fgd.patch(
        "/api/v1/system-config/sgd_diaria_regra_meia_no_retorno/", {"valor": "False"}, format="json",
    )

    assert resposta.status_code == 403
