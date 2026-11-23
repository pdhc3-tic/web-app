from datetime import date
from decimal import Decimal

import pytest
from django.db.models import ProtectedError
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound
from apps.core.tests.factories import UserFactory
from apps.sgp.budget import services as budget_service
from apps.sgp.models import TED, BudgetPool, TEDVersion
from apps.sgp.ted import services as ted_service
from apps.sgp.tests.factories import (
    BudgetPoolFactory,
    BudgetRubricaFactory,
    IndicatorFactory,
    TEDVersionFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
    WorkPlanSubmetaFactory,
    aprovar_no_ted,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel
URL = "/api/v1/sgp/ted/"
POOLS_URL = "/api/v1/sgp/orcamento/pools/"
REMANEJAR_URL = "/api/v1/sgp/orcamento/remanejamentos/"
UPLOAD_URL = "/api/v1/sgp/ted/documentos/upload-url/"
SIMULAR_URL = "/api/v1/sgp/orcamento/remanejamentos/simular/"
CHAVE = "ted/documentos/0b6f4c1e-3a5d-4f7e-9c2b-1d8e7f6a5b4c.pdf"
CHAVE_DO_ADITIVO = "ted/documentos/7c1e2d3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f.pdf"


class FakeStorage:
    def __init__(self, objects=None):
        self.objects = objects if objects is not None else {}
        self.presigned_put_calls = []

    def generate_presigned_put(self, key, content_type, size, expires_in=300):
        self.presigned_put_calls.append((key, content_type, size, expires_in))
        return "https://upload.example.com/presigned"

    def generate_presigned_get(self, key, expires_in=300):
        return f"https://download.example.com/{key}"

    def head_object(self, key):
        if key not in self.objects:
            raise StorageObjectNotFound(key)
        return self.objects[key]


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage({
        CHAVE: {"ContentType": "application/pdf", "ContentLength": 2048},
        CHAVE_DO_ADITIVO: {"ContentType": "application/pdf", "ContentLength": 2048},
    })
    for modulo in ("services", "serializers", "views"):
        monkeypatch.setattr(f"apps.sgp.ted.{modulo}.get_storage", lambda: fake)
    return fake


@pytest.fixture
def diarias():
    return BudgetRubricaFactory(slug="diarias-ted", nome="Diárias", ordem=1)


@pytest.fixture
def material():
    return BudgetRubricaFactory(slug="material-ted", nome="Material", ordem=2)


def _payload(diarias, material, **versao):
    return {
        "numero": "TED 01/2025",
        "participes": ["MDA", "UFERSA"],
        "objeto": "PDHC III",
        "versao": {
            "vigencia_inicio": "2025-11-01",
            "vigencia_fim": "2028-10-31",
            "valor_global": "1500.00",
            "rubricas": [
                {"rubrica": diarias.pk, "valor_aprovado": "1000.00"},
                {"rubrica": material.pk, "valor_aprovado": "500.00"},
            ],
            "documento_key": CHAVE,
            **versao,
        },
    }


def _aditivo(diarias, material, **campos):
    return {
        "tipo": "aditivo",
        "motivo": "Primeiro termo aditivo",
        "vigencia_inicio": "2025-11-01",
        "vigencia_fim": "2028-10-31",
        "valor_global": "2000.00",
        "rubricas": [
            {"rubrica": diarias.pk, "valor_aprovado": "1200.00"},
            {"rubrica": material.pk, "valor_aprovado": "800.00"},
        ],
        "documento_key": CHAVE_DO_ADITIVO,
        **campos,
    }


@pytest.fixture
def ted(auth_client, storage, diarias, material):
    response = auth_client.post(URL, _payload(diarias, material), format="json")
    assert response.status_code == 201, response.data
    return TED.objects.get(pk=response.data["id"])


def _versoes_url(ted):
    return f"{URL}{ted.pk}/versoes/"


def _versao_url(ted, versao=None):
    return f"{_versoes_url(ted)}{(versao or ted.versao_vigente).pk}/"


def _pedido_de_upload(**campos):
    return {"filename": "ted.pdf", "content_type": "application/pdf", "size": 1024, **campos}


def _leituras(ted):
    return [URL, f"{URL}{ted.pk}/", _versoes_url(ted), _versao_url(ted)]


def _escritas(cliente, ted, diarias, material):
    """Cadastro, edição, nova versão e upload, nessa ordem."""
    return [
        cliente.post(URL, {**_payload(diarias, material), "numero": "TED 09/2025"}, format="json"),
        cliente.patch(f"{URL}{ted.pk}/", {"objeto": "x"}, format="json"),
        cliente.post(_versoes_url(ted), _aditivo(diarias, material), format="json"),
        cliente.post(UPLOAD_URL, _pedido_de_upload(), format="json"),
    ]


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------

class TestCadastro:
    def test_cria_o_ted_com_a_versao_original_e_as_rubricas(self, auth_client, storage, diarias, material):
        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 201, response.data
        ted = TED.objects.get(pk=response.data["id"])
        versao = ted.versao_vigente
        assert (versao.numero_versao, versao.tipo) == (1, TEDVersion.Tipo.ORIGINAL)
        assert (ted.valor_global, ted.vigencia_inicio, ted.vigencia_fim) == (
            Decimal("1500.00"), date(2025, 11, 1), date(2028, 10, 31),
        )
        assert {r.rubrica_id: r.valor_aprovado for r in versao.rubricas.all()} == {
            diarias.pk: Decimal("1000.00"), material.pk: Decimal("500.00"),
        }
        assert response.data["versao_vigente"]["numero_versao"] == 1
        assert AuditLog.objects.filter(acao="TEDVersion.create", entidade_id=str(versao.pk)).exists()

    def test_segundo_ted_e_recusado(self, auth_client, ted, diarias, material):
        response = auth_client.post(URL, {**_payload(diarias, material), "numero": "TED 02/2025"}, format="json")

        assert response.status_code == 400
        assert "Já existe um TED" in str(response.data["numero"])
        assert TED.objects.count() == 1

    def test_soma_das_rubricas_diferente_do_valor_global(self, auth_client, storage, diarias, material):
        response = auth_client.post(URL, _payload(diarias, material, valor_global="1600.00"), format="json")

        assert response.status_code == 400
        assert "precisa ser igual ao valor global" in str(response.data["rubricas"])
        assert not TED.objects.exists()

    def test_rubrica_repetida(self, auth_client, storage, diarias, material):
        payload = _payload(diarias, material, rubricas=[
            {"rubrica": diarias.pk, "valor_aprovado": "750.00"},
            {"rubrica": diarias.pk, "valor_aprovado": "750.00"},
        ])

        response = auth_client.post(URL, payload, format="json")

        assert response.status_code == 400

    def test_vigencia_invertida(self, auth_client, storage, diarias, material):
        response = auth_client.post(URL, _payload(diarias, material, vigencia_fim="2025-10-31"), format="json")

        assert response.status_code == 400

    def test_documento_nao_enviado_ao_storage(self, auth_client, storage, diarias, material):
        storage.objects.pop(CHAVE)

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 400
        assert "não confirmado" in str(response.data["documento_key"])
        assert not TED.objects.exists()

    def test_chave_fora_do_padrao(self, auth_client, storage, diarias, material):
        response = auth_client.post(
            URL, _payload(diarias, material, documento_key="ufpas/1/documentos/x.pdf"), format="json",
        )

        assert response.status_code == 400
        assert not TED.objects.exists()

    def test_documento_que_nao_e_pdf(self, auth_client, storage, diarias, material):
        storage.objects[CHAVE] = {"ContentType": "image/png", "ContentLength": 10}

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 400

    def test_cadastro_com_pool_nacional_acima_do_aprovado(self, auth_client, storage, diarias, material):
        BudgetPoolFactory(
            rubrica=diarias, nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=Decimal("1000.01"),
        )

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 400
        assert "Diárias" in str(response.data["rubricas"])

    def test_edicao_muda_a_identificacao(self, auth_client, ted):
        response = auth_client.patch(
            f"{URL}{ted.pk}/", {"objeto": "Novo objeto", "participes": ["MDA", "UFERSA", "FIDA"]}, format="json",
        )

        assert response.status_code == 200
        ted.refresh_from_db()
        assert (ted.objeto, ted.participes) == ("Novo objeto", ["MDA", "UFERSA", "FIDA"])
        assert AuditLog.objects.filter(acao="TED.update", entidade_id=str(ted.pk)).exists()

    @pytest.mark.parametrize("campo, valor", [
        ("valor_global", "1.00"), ("vigencia_inicio", "2026-01-01"), ("vigencia_fim", "2030-01-01"),
    ])
    def test_edicao_recusa_o_que_vem_da_versao(self, auth_client, ted, campo, valor):
        response = auth_client.patch(f"{URL}{ted.pk}/", {"objeto": "Novo", campo: valor}, format="json")

        assert response.status_code == 400
        assert "nova versão" in str(response.data[campo])
        ted.refresh_from_db()
        assert (ted.objeto, ted.valor_global) == ("PDHC III", Decimal("1500.00"))

    def test_edicao_vazia_nao_grava_auditoria(self, auth_client, ted):
        response = auth_client.patch(f"{URL}{ted.pk}/", {}, format="json")

        assert response.status_code == 200
        assert not AuditLog.objects.filter(acao="TED.update").exists()

    def test_responsavel_pela_versao_nao_pode_ser_excluido(self, ted):
        versao = ted.versao_vigente

        with pytest.raises(ProtectedError):
            versao.registrado_por.delete()

        versao.refresh_from_db()
        assert versao.registrado_por_id is not None

    def test_storage_fora_do_ar_responde_503(self, auth_client, storage, diarias, material, monkeypatch):
        def falha(key):
            raise RuntimeError("timeout")

        monkeypatch.setattr(storage, "head_object", falha)

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 503
        assert not TED.objects.exists()

    def test_pdf_acima_de_10_mb_no_storage(self, auth_client, storage, diarias, material):
        storage.objects[CHAVE] = {"ContentType": "application/pdf", "ContentLength": 10 * 1024 * 1024 + 1}

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 400
        assert "10 MB" in str(response.data["documento_key"])

    def test_ted_nao_e_excluido(self, auth_client, ted):
        assert auth_client.delete(f"{URL}{ted.pk}/").status_code == 405


# ---------------------------------------------------------------------------
# Versões
# ---------------------------------------------------------------------------

class TestVersoes:
    def test_aditivo_vira_a_versao_2_e_preserva_a_original(self, auth_client, ted, diarias, material):
        response = auth_client.post(_versoes_url(ted), _aditivo(diarias, material), format="json")

        assert response.status_code == 201, response.data
        ted.refresh_from_db()
        original = ted.versoes.get(numero_versao=1)
        assert ted.versao_vigente.numero_versao == 2
        assert ted.valor_global == Decimal("2000.00")
        assert {r.rubrica_id: r.valor_aprovado for r in original.rubricas.all()} == {
            diarias.pk: Decimal("1000.00"), material.pk: Decimal("500.00"),
        }
        listagem = auth_client.get(_versoes_url(ted)).data
        assert listagem["count"] == 2
        assert [v["numero_versao"] for v in listagem["results"]] == [1, 2]

    def test_aditivo_sem_motivo(self, auth_client, ted, diarias, material):
        response = auth_client.post(_versoes_url(ted), _aditivo(diarias, material, motivo=""), format="json")

        assert response.status_code == 400

    def test_versao_original_so_no_cadastro(self, auth_client, ted, diarias, material):
        response = auth_client.post(_versoes_url(ted), _aditivo(diarias, material, tipo="original"), format="json")

        assert response.status_code == 400

    def test_prorrogacao_precisa_estender_o_fim(self, auth_client, ted, diarias, material):
        payload = _aditivo(diarias, material, tipo="prorrogacao", vigencia_fim="2028-10-31")

        response = auth_client.post(_versoes_url(ted), payload, format="json")

        assert response.status_code == 400
        assert "31/10/2028" in str(response.data["vigencia_fim"])

    def test_prorrogacao_que_estende_o_fim(self, auth_client, ted, diarias, material):
        payload = _aditivo(diarias, material, tipo="prorrogacao", vigencia_fim="2029-04-30")

        response = auth_client.post(_versoes_url(ted), payload, format="json")

        assert response.status_code == 201, response.data
        ted.refresh_from_db()
        assert ted.vigencia_fim == date(2029, 4, 30)

    def test_aditivo_abaixo_do_pool_nacional_distribuido(self, auth_client, ted, diarias, material):
        pool = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("1000"), usuario=UserFactory(),
        )
        payload = _aditivo(diarias, material, valor_global="1500.00", rubricas=[
            {"rubrica": diarias.pk, "valor_aprovado": "900.00"},
            {"rubrica": material.pk, "valor_aprovado": "600.00"},
        ])

        response = auth_client.post(_versoes_url(ted), payload, format="json")

        assert response.status_code == 400
        assert "Diárias" in str(response.data["rubricas"])
        ted.refresh_from_db()
        assert ted.versao_vigente.numero_versao == 1

        reducao = auth_client.patch(f"{POOLS_URL}{pool.pk}/", {"valor_alocado": "900.00"}, format="json")
        assert reducao.status_code == 200, reducao.data
        assert auth_client.post(_versoes_url(ted), payload, format="json").status_code == 201

    def test_pdf_de_outra_versao_e_recusado(self, auth_client, ted, diarias, material):
        response = auth_client.post(
            _versoes_url(ted), _aditivo(diarias, material, documento_key=CHAVE), format="json",
        )

        assert response.status_code == 400
        assert "outra versão" in str(response.data["documento_key"])

    def test_rubrica_fora_da_versao_vale_zero(self, auth_client, ted, diarias, material):
        budget_service.criar_pool(
            rubrica=material, nivel=Nivel.NACIONAL, valor_alocado=Decimal("1"), usuario=UserFactory(),
        )
        payload = _aditivo(diarias, material, valor_global="1200.00", rubricas=[
            {"rubrica": diarias.pk, "valor_aprovado": "1200.00"},
        ])

        response = auth_client.post(_versoes_url(ted), payload, format="json")

        assert response.status_code == 400
        assert "Material" in str(response.data["rubricas"])

    def test_detalhe_traz_snapshot_rubricas_e_link_do_documento(self, auth_client, ted):
        response = auth_client.get(_versao_url(ted))

        assert response.status_code == 200
        assert response.data["documento_url"] == f"https://download.example.com/{CHAVE}"
        assert len(response.data["rubricas"]) == 2
        assert "metas" in response.data["plano_snapshot"]

    def test_versao_inexistente(self, auth_client, ted):
        assert auth_client.get(f"{_versoes_url(ted)}999999/").status_code == 404

    def test_versao_nao_se_altera_nem_se_exclui_pela_api(self, auth_client, ted):
        assert auth_client.patch(_versao_url(ted), {"motivo": "x"}, format="json").status_code == 405
        assert auth_client.delete(_versao_url(ted)).status_code == 405

    def test_versao_e_imutavel_no_modelo(self, ted):
        versao = ted.versao_vigente
        versao.motivo = "Outro"
        with pytest.raises(ValueError):
            versao.save()
        with pytest.raises(ProtectedError):
            versao.delete()
        with pytest.raises(ValueError):
            versao.rubricas.first().save()


class TestSnapshotDoPlano:
    def test_snapshot_guarda_a_arvore_e_os_valores(self):
        meta = WorkPlanMetaFactory(numero=1, titulo="Meta 1")
        submeta = WorkPlanSubmetaFactory(meta=meta, numero="1.1", titulo="Formação")
        rubrica = BudgetRubricaFactory(slug="diarias-snapshot")
        acao = WorkPlanAcaoFactory(
            meta=meta, submeta=submeta, numero="1.1.1", indicador=IndicatorFactory(),
            quantidade_planejada=Decimal("10"), valor_unitario=Decimal("250.00"),
        )
        acao.rubricas_previstas.set([rubrica])

        snapshot = ted_service.gerar_snapshot_do_plano()

        no_meta = next(m for m in snapshot["metas"] if m["numero"] == 1)
        no_submeta = no_meta["submetas"][0]
        no_acao = no_submeta["acoes"][0]
        assert (no_meta["titulo"], no_submeta["numero"], no_submeta["titulo"]) == ("Meta 1", "1.1", "Formação")
        assert no_acao["numero"] == "1.1.1"
        assert no_acao["indicador"]["codigo"] == acao.indicador.codigo
        assert (no_acao["quantidade_planejada"], no_acao["valor_unitario"], no_acao["valor_total"]) == (
            "10.00", "250.00", "2500.00",
        )
        assert no_acao["rubricas_previstas"] == ["diarias-snapshot"]

    def test_snapshot_da_versao_nao_muda_com_o_plano(self, ted):
        meta = WorkPlanMetaFactory(numero=7, titulo="Criada depois")

        ted.versao_vigente.refresh_from_db()

        assert all(m["numero"] != meta.numero for m in ted.versao_vigente.plano_snapshot["metas"])


# ---------------------------------------------------------------------------
# Permissões e upload
# ---------------------------------------------------------------------------

class TestPermissoes:
    def test_super_admin_cadastra(self, auth_client_super_admin, storage, diarias, material):
        response = auth_client_super_admin.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 201

    @pytest.mark.parametrize("cliente", ["auth_client_articulador_rn", "auth_client_fgd"])
    def test_articulador_e_fgd_so_leem(self, request, ted, cliente, diarias, material):
        cliente = request.getfixturevalue(cliente)

        assert cliente.get(URL).status_code == 200
        assert cliente.get(f"{URL}{ted.pk}/").status_code == 200
        assert cliente.get(_versoes_url(ted)).status_code == 200
        assert cliente.get(_versao_url(ted)).status_code == 200
        assert cliente.patch(f"{URL}{ted.pk}/", {"objeto": "x"}, format="json").status_code == 403
        assert cliente.post(_versoes_url(ted), _aditivo(diarias, material), format="json").status_code == 403

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_sem_acesso"])
    def test_adt_e_agricultor_nao_acessam(self, request, ted, cliente, diarias, material):
        cliente = request.getfixturevalue(cliente)

        assert [cliente.get(url).status_code for url in _leituras(ted)] == [403] * 4
        assert [r.status_code for r in _escritas(cliente, ted, diarias, material)] == [403] * 4

    @pytest.mark.parametrize("cliente", ["auth_client_articulador_rn", "auth_client_fgd"])
    def test_articulador_e_fgd_nao_escrevem(self, request, ted, cliente, diarias, material):
        cliente = request.getfixturevalue(cliente)

        assert [r.status_code for r in _escritas(cliente, ted, diarias, material)] == [403] * 4

    def test_anonimo_recebe_401(self, request, ted, diarias, material):
        cliente = request.getfixturevalue("api_client")
        cliente.force_authenticate(user=None)

        assert [cliente.get(url).status_code for url in _leituras(ted)] == [401] * 4
        assert [r.status_code for r in _escritas(cliente, ted, diarias, material)] == [401] * 4

    def test_super_admin_escreve_em_todas_as_rotas(self, request, ted, diarias, material):
        cliente = request.getfixturevalue("auth_client_super_admin")

        assert [cliente.get(url).status_code for url in _leituras(ted)] == [200] * 4
        assert cliente.patch(f"{URL}{ted.pk}/", {"objeto": "x"}, format="json").status_code == 200
        assert cliente.post(_versoes_url(ted), _aditivo(diarias, material), format="json").status_code == 201
        assert cliente.post(UPLOAD_URL, _pedido_de_upload(), format="json").status_code == 200


class TestUploadDoDocumento:
    def test_devolve_url_e_chave_do_pdf(self, auth_client, storage):
        response = auth_client.post(
            f"{URL}documentos/upload-url/",
            {"filename": "ted.pdf", "content_type": "application/pdf", "size": 1024},
            format="json",
        )

        assert response.status_code == 200
        assert ted_service.PADRAO_DA_CHAVE_DO_DOCUMENTO.match(response.data["key"])
        assert storage.presigned_put_calls[0][1:3] == ("application/pdf", 1024)

    def test_recusa_o_que_nao_e_pdf(self, auth_client, storage):
        response = auth_client.post(
            f"{URL}documentos/upload-url/",
            {"filename": "ted.png", "content_type": "image/png", "size": 1024},
            format="json",
        )

        assert response.status_code == 400

    def test_recusa_acima_de_10_mb(self, auth_client, storage):
        response = auth_client.post(
            f"{URL}documentos/upload-url/",
            {"filename": "ted.pdf", "content_type": "application/pdf", "size": 10 * 1024 * 1024 + 1},
            format="json",
        )

        assert response.status_code == 400
        assert "10 MB" in str(response.data["size"])

    def test_articulador_nao_envia(self, auth_client_articulador_rn, storage):
        response = auth_client_articulador_rn.post(
            f"{URL}documentos/upload-url/",
            {"filename": "ted.pdf", "content_type": "application/pdf", "size": 1024},
            format="json",
        )

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Pool nacional contra o TED
# ---------------------------------------------------------------------------

class TestPoolNacionalContraOTED:
    def test_sem_ted_o_pool_nacional_e_recusado(self, auth_client, diarias):
        response = auth_client.post(
            POOLS_URL, {"rubrica_id": diarias.pk, "nivel": "nacional", "valor_alocado": "100.00"}, format="json",
        )

        assert response.status_code == 400
        assert "Cadastre o TED" in str(response.data["valor_alocado"])
        assert not BudgetPool.objects.exists()

    def test_acima_do_aprovado_e_recusado(self, auth_client, ted, diarias):
        response = auth_client.post(
            POOLS_URL, {"rubrica_id": diarias.pk, "nivel": "nacional", "valor_alocado": "1000.01"}, format="json",
        )

        assert response.status_code == 400
        assert "R$ 1000.00 na versão 1" in str(response.data["valor_alocado"])

    def test_igual_ao_aprovado_passa_e_registra_a_versao(self, auth_client, ted, diarias):
        response = auth_client.post(
            POOLS_URL, {"rubrica_id": diarias.pk, "nivel": "nacional", "valor_alocado": "1000.00"}, format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["ted_versao"] == ted.versao_vigente_id

    def test_rubrica_sem_valor_na_versao_vale_zero(self, auth_client, ted):
        outra = BudgetRubricaFactory()

        response = auth_client.post(
            POOLS_URL, {"rubrica_id": outra.pk, "nivel": "nacional", "valor_alocado": "0.01"}, format="json",
        )

        assert response.status_code == 400

    def test_aumento_acima_do_aprovado_e_recusado(self, auth_client, ted, diarias):
        pool = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("800"), usuario=UserFactory(),
        )

        response = auth_client.patch(f"{POOLS_URL}{pool.pk}/", {"valor_alocado": "1000.01"}, format="json")

        assert response.status_code == 400
        pool.refresh_from_db()
        assert pool.valor_alocado == Decimal("800")

    def test_aumento_depois_do_aditivo_usa_a_versao_nova(self, auth_client, ted, diarias, material):
        pool = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("1000"), usuario=UserFactory(),
        )
        auth_client.post(_versoes_url(ted), _aditivo(diarias, material), format="json")

        response = auth_client.patch(f"{POOLS_URL}{pool.pk}/", {"valor_alocado": "1200.00"}, format="json")

        assert response.status_code == 200, response.data
        ted.refresh_from_db()
        assert response.data["ted_versao"] == ted.versao_vigente_id

    def test_aditivo_regrava_a_versao_de_todos_os_pools(self, auth_client, ted, diarias, material, state_rn):
        nacional = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("1000"), usuario=UserFactory(),
        )
        estadual = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.ESTADUAL, estado=state_rn, valor_alocado=Decimal("300"),
            usuario=UserFactory(),
        )
        original = ted.versao_vigente_id

        response = auth_client.post(_versoes_url(ted), _aditivo(diarias, material), format="json")

        assert response.status_code == 201, response.data
        ted.refresh_from_db()
        assert ted.versao_vigente_id != original
        nacional.refresh_from_db()
        estadual.refresh_from_db()
        assert (nacional.ted_versao_id, estadual.ted_versao_id) == (ted.versao_vigente_id, ted.versao_vigente_id)

    def test_cadastro_aponta_os_pools_anteriores_para_a_versao_original(
        self, auth_client, storage, diarias, material, state_rn,
    ):
        anterior = BudgetPoolFactory(
            rubrica=diarias, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("10"),
        )

        response = auth_client.post(URL, _payload(diarias, material), format="json")

        assert response.status_code == 201, response.data
        anterior.refresh_from_db()
        assert anterior.ted_versao_id == response.data["versao_vigente"]["id"]

    def test_reducao_sem_ted_passa(self, auth_client, diarias):
        pool = BudgetPoolFactory(
            rubrica=diarias, nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=Decimal("500"),
        )

        response = auth_client.patch(f"{POOLS_URL}{pool.pk}/", {"valor_alocado": "400.00"}, format="json")

        assert response.status_code == 200, response.data
        assert response.data["ted_versao"] is None

    def test_pool_estadual_registra_a_versao_vigente(self, auth_client, ted, diarias, state_rn):
        budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("1000"), usuario=UserFactory(),
        )

        response = auth_client.post(
            POOLS_URL,
            {"rubrica_id": diarias.pk, "nivel": "estadual", "estado_id": state_rn.pk, "valor_alocado": "300.00"},
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["ted_versao"] == ted.versao_vigente_id

    def test_versao_do_pool_no_limite_e_acima(self, diarias):
        versao = aprovar_no_ted(diarias, Decimal("100"))
        ted = ted_service.ted_atual()

        assert ted_service.versao_do_pool(
            ted, nivel=Nivel.NACIONAL, rubrica=diarias, novo_valor=Decimal("100"),
        ) == versao
        with pytest.raises(DRFValidationError):
            ted_service.versao_do_pool(ted, nivel=Nivel.NACIONAL, rubrica=diarias, novo_valor=Decimal("100.01"))

    def test_versao_do_pool_reducao_e_outros_niveis_nao_conferem_o_teto(self, diarias):
        versao = aprovar_no_ted(diarias, Decimal("100"))
        ted = ted_service.ted_atual()

        assert ted_service.versao_do_pool(
            ted, nivel=Nivel.NACIONAL, rubrica=diarias, novo_valor=Decimal("150"), valor_atual=Decimal("200"),
        ) == versao
        assert ted_service.versao_do_pool(
            ted, nivel=Nivel.ESTADUAL, rubrica=diarias, novo_valor=Decimal("999"),
        ) == versao
        assert ted_service.versao_do_pool(
            None, nivel=Nivel.NACIONAL, rubrica=diarias, novo_valor=Decimal("1"), valor_atual=Decimal("2"),
        ) is None


class TestRemanejamentoParaOPoolNacional:
    @pytest.fixture
    def pools(self, ted, diarias, state_rn):
        nacional = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.NACIONAL, valor_alocado=Decimal("900"), usuario=UserFactory(),
        )
        estadual = budget_service.criar_pool(
            rubrica=diarias, nivel=Nivel.ESTADUAL, estado=state_rn, valor_alocado=Decimal("300"),
            usuario=UserFactory(),
        )
        return nacional, estadual

    @staticmethod
    def _payload(origem, destino, valor):
        return {
            "origem_allocation": origem.pk, "destino_allocation": destino.pk,
            "valor": valor, "justificativa": "Devolução ao nacional.",
        }

    def test_acima_do_aprovado_e_recusado(self, auth_client, pools):
        nacional, estadual = pools

        response = auth_client.post(REMANEJAR_URL, self._payload(estadual, nacional, "100.01"), format="json")

        assert response.status_code == 400
        assert "Excede o valor aprovado no TED" in str(response.data["valor"])
        nacional.refresh_from_db()
        estadual.refresh_from_db()
        assert (nacional.valor_alocado, estadual.valor_alocado) == (Decimal("900"), Decimal("300"))

    def test_ate_o_aprovado_passa_e_registra_a_versao(self, auth_client, ted, pools):
        nacional, estadual = pools

        response = auth_client.post(REMANEJAR_URL, self._payload(estadual, nacional, "100.00"), format="json")

        assert response.status_code == 201, response.data
        nacional.refresh_from_db()
        assert (nacional.valor_alocado, nacional.ted_versao_id) == (Decimal("1000"), ted.versao_vigente_id)

    def test_simulacao_recusa_igual(self, auth_client, pools):
        nacional, estadual = pools

        response = auth_client.post(SIMULAR_URL, self._payload(estadual, nacional, "100.01"), format="json")

        assert response.status_code == 400
        assert "Excede o valor aprovado no TED" in str(response.data["valor"])

    def test_remanejamento_grava_a_versao_vigente_nos_dois_pools(
        self, auth_client, ted, pools, diarias, material,
    ):
        nacional, estadual = pools
        auth_client.post(_versoes_url(ted), _aditivo(diarias, material), format="json")
        ted.refresh_from_db()

        response = auth_client.post(REMANEJAR_URL, self._payload(nacional, estadual, "50.00"), format="json")

        assert response.status_code == 201, response.data
        nacional.refresh_from_db()
        estadual.refresh_from_db()
        assert (nacional.ted_versao_id, estadual.ted_versao_id) == (ted.versao_vigente_id, ted.versao_vigente_id)


class TestFactoryDoTED:
    def test_factory_vira_a_versao_vigente(self):
        versao = TEDVersionFactory(valor_global=Decimal("10"))

        versao.ted.refresh_from_db()
        assert versao.ted.versao_vigente == versao
