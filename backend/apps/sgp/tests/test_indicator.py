"""Catálogo de Indicadores (SGP §5.4, RF20)."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import Indicator
from apps.sgp.tests.factories import (
    ActivityFactory,
    IndicatorFactory,
    UPFFactory,
    WorkPlanAcaoFactory,
    WorkPlanSubmetaFactory,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgp/indicadores/"


def _detalhe(pk):
    return f"{URL}{pk}/"


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


@pytest.fixture
def payload():
    return {
        "codigo": "ind-teste",
        "nome": "Oficinas realizadas",
        "unidade_medida": "evento",
        "forma_apuracao": "contagem_atividades",
        "categoria": "formacao",
        "ods_ids": [1, 2],
        "desagregacoes": ["genero", "territorio"],
    }


class TestCadastro:
    def test_cria_indicador_normaliza_codigo_e_audita(self, auth_client, payload, usuario):
        response = auth_client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["codigo"] == "IND-TESTE"
        assert response.data["total_acoes"] == 0
        indicador = Indicator.objects.get(pk=response.data["id"])
        assert indicador.criado_por == usuario
        assert AuditLog.objects.filter(acao="Indicator.create", entidade_id=str(indicador.pk)).exists()

    def test_codigo_duplicado_retorna_400(self, auth_client, payload):
        auth_client.post(URL, payload, format="json")

        response = auth_client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "codigo" in response.data

    def test_codigo_duplicado_com_outra_caixa_retorna_400(self, auth_client, payload):
        auth_client.post(URL, {**payload, "codigo": "IND-TESTE"}, format="json")

        response = auth_client.post(URL, {**payload, "codigo": " ind-teste "}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "codigo" in response.data

    @pytest.mark.parametrize("campo,valor", [
        ("ods_ids", [99]),
        ("ods_ids", "1"),
        ("desagregacoes", ["idade"]),
        ("desagregacoes", "genero"),
        ("unidade_medida", "litro"),
        ("forma_apuracao", "media"),
    ])
    def test_valores_invalidos_retornam_400(self, auth_client, payload, campo, valor):
        response = auth_client.post(URL, {**payload, campo: valor}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert campo in response.data

    def test_catalogo_inicial_vem_da_migration(self):
        assert Indicator.objects.filter(codigo="IND-FAM", forma_apuracao="soma_ufpas").exists()
        assert Indicator.objects.filter(codigo="IND-UNI", forma_apuracao="manual").exists()


class TestPermissoes:
    @pytest.mark.parametrize("fixture", [
        "usuario_adt_rn", "usuario_articulador_rn", "usuario_fgd",
    ])
    def test_outros_perfis_leem_mas_nao_escrevem(self, request, payload, fixture):
        cliente = _cliente(request.getfixturevalue(fixture))

        assert cliente.get(URL).status_code == status.HTTP_200_OK
        assert cliente.post(URL, payload, format="json").status_code == status.HTTP_403_FORBIDDEN

    def test_super_admin_escreve(self, payload, usuario_super_admin):
        response = _cliente(usuario_super_admin).post(URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED


class TestFiltros:
    def test_filtros(self, auth_client):
        oficina = IndicatorFactory(codigo="TST-OFI", nome="Ypsilon oficinas", categoria="formacao")
        familias = IndicatorFactory(
            codigo="TST-FAM", nome="Zeta acolhidas", forma_apuracao="soma_ufpas", ativo=False
        )

        def ids(params):
            return {item["id"] for item in auth_client.get(URL, {**params, "page_size": 200}).data["results"]}

        assert ids({"q": "tst-ofi"}) == {oficina.pk}
        assert ids({"q": "zeta"}) == {familias.pk}
        assert familias.pk in ids({"ativo": "false"})
        assert familias.pk not in ids({"ativo": "true"})
        assert ids({"forma_apuracao": "soma_ufpas", "q": "TST"}) == {familias.pk}
        assert ids({"categoria": "formacao", "q": "TST"}) == {oficina.pk}


class TestExclusaoEInativacao:
    def test_excluir_em_uso_retorna_409(self, auth_client):
        acao = WorkPlanAcaoFactory()

        response = auth_client.delete(_detalhe(acao.indicador_id))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "indicador_em_uso"
        assert Indicator.objects.filter(pk=acao.indicador_id).exists()

    def test_excluir_sem_acoes(self, auth_client):
        indicador = IndicatorFactory()

        assert auth_client.delete(_detalhe(indicador.pk)).status_code == status.HTTP_204_NO_CONTENT
        assert AuditLog.objects.filter(acao="Indicator.delete").exists()

    def test_inativar_em_uso_e_permitido(self, auth_client):
        acao = WorkPlanAcaoFactory()

        response = auth_client.patch(_detalhe(acao.indicador_id), {"ativo": False}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_acoes"] == 1

    def test_indicador_inativo_nao_entra_em_acao_nova(self, auth_client):
        submeta = WorkPlanSubmetaFactory()
        inativo = IndicatorFactory(ativo=False)

        response = auth_client.post("/api/v1/acoes/", {
            "submeta": submeta.pk,
            "indicador": inativo.pk,
            "numero": f"{submeta.numero}.1",
            "descricao": "Ação",
            "quantidade_planejada": "1.00",
            "valor_unitario": "1.00",
            "data_inicio": str(submeta.data_inicio),
            "data_fim": str(submeta.data_fim),
        }, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "indicador" in response.data

    def test_acao_que_ja_usa_indicador_inativo_continua_editavel(self, auth_client):
        acao = WorkPlanAcaoFactory()
        Indicator.objects.filter(pk=acao.indicador_id).update(ativo=False)

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"descricao": "Nova descrição"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK, response.data

    def test_trocar_para_indicador_inativo_retorna_400(self, auth_client):
        acao = WorkPlanAcaoFactory()
        inativo = IndicatorFactory(ativo=False)

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"indicador": inativo.pk}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTrocaDeFormaDeApuracao:
    @pytest.fixture
    def acao_com_ufpas(self, municipio_rn):
        acao = WorkPlanAcaoFactory(indicador=IndicatorFactory(forma_apuracao="contagem_atividades"))
        upf = UPFFactory(municipio=municipio_rn)
        for _ in range(3):
            atividade = ActivityFactory(acao=acao, status="concluido", municipio=municipio_rn)
            atividade.upfs_participantes.add(upf)
        acao.refresh_from_db()
        assert acao.quantidade_realizada == 3
        return acao

    def test_sem_confirmacao_retorna_409_e_nao_altera(self, auth_client, acao_com_ufpas):
        indicador = acao_com_ufpas.indicador

        response = auth_client.patch(
            _detalhe(indicador.pk), {"forma_apuracao": "soma_ufpas"}, format="json"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "confirmacao_necessaria"
        assert "1 Ação" in response.data["message"]
        indicador.refresh_from_db()
        assert indicador.forma_apuracao == "contagem_atividades"

    def test_com_confirmacao_recalcula_e_audita(self, auth_client, acao_com_ufpas):
        indicador = acao_com_ufpas.indicador

        response = auth_client.patch(
            _detalhe(indicador.pk),
            {"forma_apuracao": "soma_ufpas", "confirmar_recalculo": True},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        acao_com_ufpas.refresh_from_db()
        assert acao_com_ufpas.quantidade_realizada == 1
        registro = AuditLog.objects.get(acao="Indicator.forma_apuracao_alterada")
        assert registro.valores_anteriores["forma_apuracao"] == "contagem_atividades"
        assert registro.valores_novos["forma_apuracao"] == "soma_ufpas"

    def test_sem_acoes_nao_pede_confirmacao(self, auth_client):
        indicador = IndicatorFactory()

        response = auth_client.patch(
            _detalhe(indicador.pk), {"forma_apuracao": "manual"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK

    def test_editar_outros_campos_em_uso_nao_pede_confirmacao(self, auth_client, acao_com_ufpas):
        response = auth_client.patch(
            _detalhe(acao_com_ufpas.indicador_id), {"nome": "Outro nome"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert AuditLog.objects.filter(acao="Indicator.update").exists()
