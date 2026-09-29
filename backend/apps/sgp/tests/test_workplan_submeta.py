"""CRUD de Submetas (SGP §5.3, RF18) e consistência com Meta e Ações."""
from datetime import date

import pytest
from django.contrib.admin.sites import site
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import Indicator, WorkPlanSubmeta
from apps.sgp.tests.factories import (
    ActivityFactory,
    IndicatorFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
    WorkPlanSubmetaFactory,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgp/submetas/"


def _detalhe(pk):
    return f"{URL}{pk}/"


@pytest.fixture
def meta(usuario):
    return WorkPlanMetaFactory(
        numero=1,
        titulo="Meta 1",
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 12, 31),
        criado_por=usuario,
    )


@pytest.fixture
def payload(meta):
    return {
        "meta": meta.pk,
        "numero": "1.1",
        "titulo": "Formação",
        "data_inicio": "2026-02-01",
        "data_fim": "2026-11-30",
    }


@pytest.fixture
def submeta(meta):
    return WorkPlanSubmetaFactory(
        meta=meta, numero="1.1",
        data_inicio=date(2026, 2, 1), data_fim=date(2026, 11, 30),
    )


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


class TestCriacao:
    def test_cria_submeta_e_registra_auditoria(self, auth_client, payload, usuario):
        response = auth_client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED, response.data
        submeta = WorkPlanSubmeta.objects.get(pk=response.data["id"])
        assert submeta.criado_por == usuario
        assert AuditLog.objects.filter(
            acao="WorkPlanSubmeta.create", entidade="WorkPlanSubmeta", entidade_id=str(submeta.pk)
        ).exists()

    def test_numero_duplicado_na_mesma_meta_retorna_400(self, auth_client, payload):
        auth_client.post(URL, payload, format="json")

        response = auth_client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data

    def test_prefixo_diferente_do_numero_da_meta_retorna_400(self, auth_client, payload):
        response = auth_client.post(URL, {**payload, "numero": "2.1"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data

    @pytest.mark.parametrize("numero", ["1", "1.a", "1.1.1", "a.1"])
    def test_formato_invalido_retorna_400(self, auth_client, payload, numero):
        response = auth_client.post(URL, {**payload, "numero": numero}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data

    @pytest.mark.parametrize("inicio,fim", [
        ("2025-12-31", "2026-06-30"),
        ("2026-02-01", "2027-01-01"),
    ])
    def test_periodo_fora_da_meta_retorna_400(self, auth_client, payload, inicio, fim):
        response = auth_client.post(
            URL, {**payload, "data_inicio": inicio, "data_fim": fim}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "data_inicio" in response.data

    def test_fim_antes_do_inicio_retorna_400(self, auth_client, payload):
        response = auth_client.post(
            URL, {**payload, "data_inicio": "2026-06-01", "data_fim": "2026-05-01"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_datas_sao_obrigatorias(self, auth_client, payload):
        sem_datas = {k: v for k, v in payload.items() if not k.startswith("data_")}

        response = auth_client.post(URL, sem_datas, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert {"data_inicio", "data_fim"} <= set(response.data)

    def test_responsavel_precisa_ser_da_ugp(self, auth_client, payload, usuario_adt_rn):
        response = auth_client.post(
            URL, {**payload, "responsavel": usuario_adt_rn.pk}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "responsavel" in response.data

    def test_responsavel_da_ugp_e_aceito(self, auth_client, payload, usuario):
        response = auth_client.post(URL, {**payload, "responsavel": usuario.pk}, format="json")

        assert response.status_code == status.HTTP_201_CREATED, response.data


class TestPermissoes:
    @pytest.mark.parametrize("fixture", [
        "usuario_adt_rn", "usuario_articulador_rn", "usuario_fgd", "usuario_sem_acesso",
    ])
    def test_sem_escrita_para_outros_perfis(self, request, payload, fixture):
        cliente = _cliente(request.getfixturevalue(fixture))

        assert cliente.post(URL, payload, format="json").status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("fixture", ["usuario_adt_rn", "usuario_articulador_rn", "usuario_fgd"])
    def test_sem_edicao_nem_exclusao_para_outros_perfis(self, request, meta, fixture):
        submeta = WorkPlanSubmetaFactory(meta=meta)
        cliente = _cliente(request.getfixturevalue(fixture))

        assert (
            cliente.patch(_detalhe(submeta.pk), {"titulo": "X"}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )
        assert cliente.delete(_detalhe(submeta.pk)).status_code == status.HTTP_403_FORBIDDEN

    def test_ugp_e_super_admin_escrevem(self, auth_client, payload, usuario_super_admin):
        assert auth_client.post(URL, payload, format="json").status_code == status.HTTP_201_CREATED
        segunda = {**payload, "numero": "1.2"}
        super_admin = _cliente(usuario_super_admin)
        response = super_admin.post(URL, segunda, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        assert (
            super_admin.patch(_detalhe(response.data["id"]), {"titulo": "Y"}, format="json").status_code
            == status.HTTP_200_OK
        )


class TestLeitura:
    def test_adt_so_lista_submetas_com_acoes_no_seu_territorio(
        self, auth_client_adt_rn, meta, municipio_rn, municipio_ce
    ):
        visivel = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        oculta = WorkPlanSubmetaFactory(meta=meta, numero="1.2")
        ActivityFactory(acao=WorkPlanAcaoFactory(submeta=visivel, meta=meta), municipio=municipio_rn)
        ActivityFactory(acao=WorkPlanAcaoFactory(submeta=oculta, meta=meta), municipio=municipio_ce)

        response = auth_client_adt_rn.get(URL)

        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.data["results"]] == [visivel.pk]

    def test_filtro_por_meta(self, auth_client, meta):
        da_meta = WorkPlanSubmetaFactory(meta=meta)
        WorkPlanSubmetaFactory(meta=WorkPlanMetaFactory(numero=2))

        response = auth_client.get(URL, {"meta": meta.pk})

        assert [item["id"] for item in response.data["results"]] == [da_meta.pk]

    def test_detalhe_traz_acoes_e_consolidados(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        WorkPlanAcaoFactory(submeta=submeta, meta=meta, quantidade_planejada=10, valor_unitario=100)
        WorkPlanAcaoFactory(submeta=submeta, meta=meta, quantidade_planejada=5, valor_unitario=20)

        response = auth_client.get(_detalhe(submeta.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["acoes"]) == 2
        assert response.data["quantidade_planejada"] == "15.00"
        assert response.data["valor_total"] == "1100.00"
        assert response.data["status_execucao"] == "no_prazo"


class TestEdicaoEExclusao:
    def test_excluir_com_acoes_retorna_409(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta)
        WorkPlanAcaoFactory(submeta=submeta, meta=meta)

        response = auth_client.delete(_detalhe(submeta.pk))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "submeta_com_acoes"
        assert WorkPlanSubmeta.objects.filter(pk=submeta.pk).exists()

    def test_excluir_sem_acoes_registra_auditoria(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta)

        assert auth_client.delete(_detalhe(submeta.pk)).status_code == status.HTTP_204_NO_CONTENT
        assert AuditLog.objects.filter(acao="WorkPlanSubmeta.delete").exists()

    def test_renumerar_submeta_sem_acoes_audita_antes_e_depois(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1")

        response = auth_client.patch(_detalhe(submeta.pk), {"numero": "1.4"}, format="json")

        assert response.status_code == status.HTTP_200_OK, response.data
        registro = AuditLog.objects.get(acao="WorkPlanSubmeta.update")
        assert registro.valores_anteriores["numero"] == "1.1"
        assert registro.valores_novos["numero"] == "1.4"

    @pytest.mark.parametrize("mudanca", ["numero", "meta"])
    def test_submeta_com_acoes_nao_muda_de_numero_nem_de_meta(self, auth_client, meta, mudanca):
        outra = WorkPlanMetaFactory(
            numero=2, data_inicio=meta.data_inicio, data_fim=meta.data_fim
        )
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        dados = {"numero": {"numero": "1.4"}, "meta": {"meta": outra.pk, "numero": "2.1"}}[mudanca]

        response = auth_client.patch(_detalhe(submeta.pk), dados, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data
        acao.refresh_from_db()
        assert (acao.numero, acao.meta_id) == ("1.1.1", meta.pk)

    def test_novo_periodo_nao_pode_deixar_acoes_de_fora(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta)
        acao = WorkPlanAcaoFactory(
            submeta=submeta, meta=meta,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 9, 30),
        )

        response = auth_client.patch(
            _detalhe(submeta.pk), {"data_fim": "2026-06-30"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert acao.numero in str(response.data["data_inicio"])


class TestConsistenciaComMeta:
    def test_periodo_da_meta_nao_pode_deixar_submetas_de_fora(self, auth_client, meta):
        WorkPlanSubmetaFactory(
            meta=meta, numero="1.1",
            data_inicio=date(2026, 6, 1), data_fim=date(2026, 12, 31),
        )

        response = auth_client.patch(
            f"/api/v1/metas/{meta.pk}/", {"data_fim": "2026-10-31"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "1.1" in str(response.data["data_inicio"])

    def test_numero_da_meta_com_submetas_nao_muda(self, auth_client, meta):
        WorkPlanSubmetaFactory(meta=meta)

        response = auth_client.patch(f"/api/v1/metas/{meta.pk}/", {"numero": 5}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data

    def test_status_da_meta_vem_das_submetas(self, meta):
        concluida = WorkPlanSubmetaFactory(meta=meta)
        WorkPlanAcaoFactory(submeta=concluida, meta=meta, quantidade_planejada=0)
        assert meta.status_calculado == "concluida"

        pendente = WorkPlanSubmetaFactory(meta=meta)
        WorkPlanAcaoFactory(submeta=pendente, meta=meta, quantidade_planejada=5)
        assert meta.status_calculado == "no_prazo"

        meta.data_fim = date(2026, 1, 31)
        assert meta.status_calculado == "em_atraso"

    def test_detalhe_da_meta_so_traz_submetas_do_escopo(
        self, auth_client_adt_rn, meta, municipio_rn, municipio_ce
    ):
        visivel = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        oculta = WorkPlanSubmetaFactory(meta=meta, numero="1.2")
        ActivityFactory(acao=WorkPlanAcaoFactory(submeta=visivel, meta=meta), municipio=municipio_rn)
        ActivityFactory(acao=WorkPlanAcaoFactory(submeta=oculta, meta=meta), municipio=municipio_ce)

        response = auth_client_adt_rn.get(f"/api/v1/metas/{meta.pk}/")

        assert [s["numero"] for s in response.data["submetas"]] == ["1.1"]
        assert len(response.data["acoes"]) == 1

    def test_detalhe_da_meta_traz_submetas(self, auth_client, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        WorkPlanAcaoFactory(submeta=submeta, meta=meta)

        response = auth_client.get(f"/api/v1/metas/{meta.pk}/")

        assert [s["numero"] for s in response.data["submetas"]] == ["1.1"]
        assert len(response.data["submetas"][0]["acoes"]) == 1


class TestAcaoNaSubmeta:
    def _payload(self, submeta, indicador, **extra):
        return {
            "submeta": submeta.pk,
            "indicador": indicador.pk,
            "numero": "1.1.1",
            "descricao": "Oficinas",
            "quantidade_planejada": "10.00",
            "valor_unitario": "100.00",
            "data_inicio": "2026-03-01",
            "data_fim": "2026-10-31",
            **extra,
        }

    def test_meta_e_derivada_da_submeta(self, auth_client, submeta, meta):
        response = auth_client.post(
            "/api/v1/acoes/", self._payload(submeta, IndicatorFactory()), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["meta"] == meta.pk
        assert response.data["submeta_numero"] == "1.1"

    def test_criar_com_submeta_de_outra_meta_retorna_400(self, auth_client, submeta):
        outra = WorkPlanMetaFactory(numero=2)

        response = auth_client.post(
            "/api/v1/acoes/", self._payload(submeta, IndicatorFactory(), meta=outra.pk),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "meta" in response.data

    def test_editar_com_submeta_de_outra_meta_retorna_400(self, auth_client, submeta, meta):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        outra = WorkPlanMetaFactory(numero=2)

        response = auth_client.patch(f"/api/v1/acoes/{acao.pk}/", {"meta": outra.pk}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "meta" in response.data
        acao.refresh_from_db()
        assert acao.meta_id == meta.pk

    def test_prefixo_de_outra_submeta_retorna_400(self, auth_client, submeta):
        response = auth_client.post(
            "/api/v1/acoes/", self._payload(submeta, IndicatorFactory(), numero="1.2.1"),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data

    def test_periodo_fora_da_submeta_retorna_400(self, auth_client, submeta):
        response = auth_client.post(
            "/api/v1/acoes/",
            self._payload(submeta, IndicatorFactory(), data_fim="2026-12-15"),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "data_inicio" in response.data

    def test_mover_acao_para_submeta_de_outro_prefixo_sem_renumerar_retorna_400(
        self, auth_client, submeta, meta
    ):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        outra_meta = WorkPlanMetaFactory(numero=4, data_inicio=meta.data_inicio, data_fim=meta.data_fim)
        destino = WorkPlanSubmetaFactory(meta=outra_meta, numero="4.1")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"submeta": destino.pk}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "numero" in response.data
        acao.refresh_from_db()
        assert acao.submeta_id == submeta.pk

    def test_submeta_indicador_e_datas_obrigatorios(self, auth_client, submeta):
        payload = self._payload(submeta, IndicatorFactory())
        for campo in ("submeta", "indicador", "data_inicio", "data_fim"):
            del payload[campo]

        response = auth_client.post("/api/v1/acoes/", payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert {"submeta", "indicador", "data_inicio", "data_fim"} <= set(response.data)

    def test_filtros_por_submeta_e_indicador(self, auth_client, submeta, meta):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta)
        WorkPlanAcaoFactory(meta=meta)

        por_submeta = auth_client.get("/api/v1/acoes/", {"submeta": submeta.pk})
        por_indicador = auth_client.get("/api/v1/acoes/", {"indicador": acao.indicador_id})

        assert [item["id"] for item in por_submeta.data["results"]] == [acao.pk]
        assert [item["id"] for item in por_indicador.data["results"]] == [acao.pk]

    def test_alias_tipo_unidade_display_traz_nome_do_indicador(self, auth_client, submeta, meta):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta)

        response = auth_client.get(f"/api/v1/acoes/{acao.pk}/")

        assert response.data["tipo_unidade_display"] == acao.indicador.nome
        assert response.data["indicador_detalhe"]["codigo"] == acao.indicador.codigo


class TestRegrasValemForaDaApi:
    """As regras moram nos models: o admin do Django (e qualquer outro caminho
    que salve pelo ORM) não consegue deixar a hierarquia inconsistente."""

    def test_submeta_com_acoes_nao_muda_de_numero_no_clean(self, submeta, meta):
        WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        submeta.numero = "1.4"

        with pytest.raises(ValidationError) as erro:
            submeta.clean()

        assert "numero" in erro.value.message_dict

    def test_responsavel_fora_da_ugp_nao_passa_no_clean(self, meta, usuario_adt_rn):
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1", responsavel=None)
        submeta.responsavel = usuario_adt_rn

        with pytest.raises(ValidationError) as erro:
            submeta.full_clean()

        assert "responsavel" in erro.value.message_dict

    def test_periodo_da_submeta_nao_deixa_acoes_de_fora(self, meta):
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        WorkPlanAcaoFactory(
            submeta=submeta, meta=meta, numero="1.1.1",
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 9, 30),
        )
        submeta.data_fim = date(2026, 6, 30)

        with pytest.raises(ValidationError) as erro:
            submeta.clean()

        assert "1.1.1" in erro.value.message_dict["data_inicio"][0]

    def test_meta_com_submetas_nao_muda_de_numero(self, meta):
        WorkPlanSubmetaFactory(meta=meta, numero="1.1")
        meta.numero = 5

        with pytest.raises(ValidationError) as erro:
            meta.clean()

        assert "numero" in erro.value.message_dict

    def test_acao_nao_troca_para_indicador_inativo(self, submeta, meta):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        acao.indicador = IndicatorFactory(ativo=False)

        with pytest.raises(ValidationError) as erro:
            acao.clean()

        assert "indicador" in erro.value.message_dict

    def test_acao_que_ja_usa_indicador_inativo_continua_valida(self, submeta, meta):
        acao = WorkPlanAcaoFactory(submeta=submeta, meta=meta, numero="1.1.1")
        Indicator.objects.filter(pk=acao.indicador_id).update(ativo=False)
        acao.refresh_from_db()

        acao.clean()

    def test_admin_nao_troca_forma_de_apuracao_de_indicador_em_uso(self, rf, submeta, meta):
        admin_do_indicador = site._registry[Indicator]
        em_uso = WorkPlanAcaoFactory(submeta=submeta, meta=meta).indicador
        livre = IndicatorFactory()

        assert "forma_apuracao" in admin_do_indicador.get_readonly_fields(rf.get("/"), em_uso)
        assert "forma_apuracao" not in admin_do_indicador.get_readonly_fields(rf.get("/"), livre)
