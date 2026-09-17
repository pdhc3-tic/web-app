"""
Correção de auditoria dos critérios de aceitação das Issues #186/#187:

- GET /api/v1/sca/sync/pull não pode entregar `saude`/`cor_raca` a perfil
  sem permissão de leitura sobre esses campos (matriz de
  `apps.core.sensitive_fields`) — antes, qualquer técnico autenticado com
  território recebia os dois campos, independentemente do perfil.
- POST /api/v1/sca/sync/push não pode aceitar (e aplicar em silêncio) a
  escrita de `saude`/`cor_raca` por quem não tem essa mesma permissão.
- Conflito de sincronização em `saude`/`cor_raca` precisa ser tratado como
  campo sensível (Estratégia 3): fica pendente de resolução manual, não é
  aplicado automaticamente por last-write-wins.
"""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sca.models import ConflictLog
from apps.sca.tests.conftest import payload_upf
from apps.sca.tests.test_sync_push import build_item, post_batch
from apps.sca.tests.test_sync_pull import get_pull
from apps.sgp.models import MembroFamilia
from apps.sgp.tests.factories import MembroFactory, UPFFactory

pytestmark = pytest.mark.django_db


# ──────────────────────────────────────────────────────────────
# Fixtures locais — perfis sem acesso a saude/cor_raca (fgd, agricultor),
# mas com território vinculado (o escopo territorial do SCA não depende do
# perfil — ver apps.core.services.permissions.user_territories).
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def fgd_rn(db, territory):
    role = RoleFactory(slug="fgd", nome="FGD")
    return UserFactory(email="fgd@test.com", nome="FGD RN", profiles=[(role, territory)])


@pytest.fixture
def auth_client_fgd(api_client, fgd_rn):
    api_client.force_authenticate(user=fgd_rn)
    return api_client


@pytest.fixture
def agricultor_rn(db, territory):
    role = RoleFactory(slug="agricultor", nome="Agricultor")
    return UserFactory(email="agricultor@test.com", nome="Agricultor RN", profiles=[(role, territory)])


@pytest.fixture
def auth_client_agricultor(api_client, agricultor_rn):
    api_client.force_authenticate(user=agricultor_rn)
    return api_client


@pytest.fixture
def upf_com_membro(db, municipio, projeto):
    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    upf.titular.cor_raca = 3
    upf.titular.saude = ["hipertensao"]
    upf.titular.save(update_fields=["cor_raca", "saude"])
    MembroFactory(
        upf=upf, grau_parentesco="filho", cor_raca=2, saude=["diabetes"], uuid_local=uuid4(),
    )
    return upf


# ──────────────────────────────────────────────────────────────
# Pull — omissão condicional (Issue #192)
# ──────────────────────────────────────────────────────────────

class TestPullRespeitaMatrizDePermissao:
    def test_perfil_sem_permissao_nao_recebe_saude_nem_cor_raca(
        self, auth_client_fgd, upf_com_membro
    ):
        response = get_pull(auth_client_fgd)

        assert response.status_code == 200
        (upf_data,) = [u for u in response.data["upfs"] if u["id"] == upf_com_membro.pk]
        assert "cor_raca" not in upf_data["titular"]
        assert "saude" not in upf_data["titular"]
        assert upf_data["titular"]["nome_completo"] == upf_com_membro.titular.nome_completo

        membros_filho = [m for m in response.data["members"] if m["upf"] == upf_com_membro.pk]
        assert membros_filho
        for membro_data in membros_filho:
            assert "cor_raca" not in membro_data
            assert "saude" not in membro_data

    def test_agricultor_tambem_nao_recebe_campos_sensiveis(
        self, auth_client_agricultor, upf_com_membro
    ):
        response = get_pull(auth_client_agricultor)
        (upf_data,) = [u for u in response.data["upfs"] if u["id"] == upf_com_membro.pk]
        assert "cor_raca" not in upf_data["titular"]
        assert "saude" not in upf_data["titular"]

    def test_campos_sensiveis_somem_nunca_viram_null(self, auth_client_fgd, upf_com_membro):
        """Mesmo contrato do resto do sistema: ausência da chave, não `null`
        nem placeholder — não pode sugerir a quem não tem permissão que o
        dado existe."""
        response = get_pull(auth_client_fgd)
        (upf_data,) = [u for u in response.data["upfs"] if u["id"] == upf_com_membro.pk]
        assert "cor_raca" not in upf_data["titular"].keys()

    @pytest.mark.parametrize("client_fixture", ["auth_client", "auth_client_super_admin"])
    def test_perfil_autorizado_continua_recebendo(
        self, client_fixture, request, upf_com_membro
    ):
        """`auth_client` (conftest) autentica como adt-acr — perfil com
        permissão sobre saude/cor_raca na matriz."""
        client = request.getfixturevalue(client_fixture)
        response = get_pull(client)
        (upf_data,) = [u for u in response.data["upfs"] if u["id"] == upf_com_membro.pk]
        assert upf_data["titular"]["cor_raca"] == 3
        assert upf_data["titular"]["saude"] == ["hipertensao"]


# ──────────────────────────────────────────────────────────────
# Push — rejeição explícita de escrita não autorizada (Issue #192)
# ──────────────────────────────────────────────────────────────

class TestPushRecusaEscritaNaoAutorizada:
    def test_criacao_de_membro_com_cor_raca_por_fgd_e_recusada(
        self, auth_client_fgd, upf_com_membro
    ):
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_com_membro.pk,
                "nome_completo": "Novo Filho",
                "grau_parentesco": "filho",
                "cor_raca": 1,
            },
        )
        response = post_batch(auth_client_fgd, [item])

        assert response.status_code == 200
        resultado = response.data["resultados"][0]
        assert resultado["status"] == "erro"
        assert "CAMPO_SENSIVEL_NAO_AUTORIZADO" in resultado["erro"]
        assert not MembroFamilia.objects.filter(nome_completo="Novo Filho").exists()

    def test_criacao_de_membro_com_saude_por_agricultor_e_recusada(
        self, auth_client_agricultor, upf_com_membro
    ):
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_com_membro.pk,
                "nome_completo": "Novo Filho Saude",
                "grau_parentesco": "filho",
                "saude": ["gestante"],
            },
        )
        response = post_batch(auth_client_agricultor, [item])

        resultado = response.data["resultados"][0]
        assert resultado["status"] == "erro"
        assert "CAMPO_SENSIVEL_NAO_AUTORIZADO" in resultado["erro"]

    def test_edicao_de_upf_com_cor_raca_do_titular_por_fgd_e_recusada(
        self, auth_client_fgd, upf_com_membro, municipio, projeto
    ):
        upf = upf_com_membro
        cor_raca_original = upf.titular.cor_raca

        base = payload_upf(projeto, municipio)
        base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": upf.titular.cpf}
        payload = dict(base)
        payload["titular"] = dict(base["titular"], cor_raca=4)

        item = build_item(
            entidade="upf",
            operacao="update",
            uuid_local=upf.uuid_local,
            payload=payload,
            base=base,
            updated_at=timezone.now(),
        )
        response = post_batch(auth_client_fgd, [item])

        assert response.data["resultados"][0]["status"] == "erro"
        upf.titular.refresh_from_db()
        assert upf.titular.cor_raca == cor_raca_original

    def test_criacao_sem_campos_sensiveis_continua_funcionando_para_fgd(
        self, auth_client_fgd, upf_com_membro
    ):
        """Regressão: o bloqueio é só sobre saude/cor_raca — o restante do
        sync continua funcionando para perfis sem essa permissão."""
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_com_membro.pk,
                "nome_completo": "Filho Sem Sensivel",
                "grau_parentesco": "filho",
            },
        )
        response = post_batch(auth_client_fgd, [item])

        assert response.data["resultados"][0]["status"] == "ok"
        assert MembroFamilia.objects.filter(nome_completo="Filho Sem Sensivel").exists()

    def test_usuario_autorizado_nao_e_afetado(self, auth_client, upf_com_membro):
        """`auth_client` autentica como adt-acr — tem permissão sobre
        saude/cor_raca e continua escrevendo normalmente."""
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_com_membro.pk,
                "nome_completo": "Filho Autorizado",
                "grau_parentesco": "filho",
                "cor_raca": 2,
            },
        )
        response = post_batch(auth_client, [item])

        assert response.data["resultados"][0]["status"] == "ok"
        criado = MembroFamilia.objects.get(nome_completo="Filho Autorizado")
        assert criado.cor_raca == 2


# ──────────────────────────────────────────────────────────────
# Conflito em saude/cor_raca — tratado como campo sensível (Estratégia 3)
# ──────────────────────────────────────────────────────────────

class TestConflitoEmCampoSensivelDeSaudeCorRaca:
    def test_conflito_em_saude_do_membro_fica_pendente_e_nao_aplica(
        self, auth_client, articulador, upf_com_membro
    ):
        membro = MembroFamilia.objects.filter(upf=upf_com_membro, grau_parentesco="filho").first()
        membro.uuid_local = uuid4()
        membro.save(update_fields=["uuid_local"])
        MembroFamilia.objects.filter(pk=membro.pk).update(saude=["asma"])

        base = {
            "upf": upf_com_membro.pk,
            "nome_completo": membro.nome_completo,
            "grau_parentesco": "filho",
            "saude": ["diabetes"],
        }
        payload = dict(base, saude=["gestante"])

        item = build_item(
            entidade="member",
            operacao="update",
            uuid_local=membro.uuid_local,
            payload=payload,
            base=base,
            updated_at=timezone.now() + timedelta(minutes=1),
        )

        with patch("apps.sca.tasks.notify_articulador_sync_conflict.delay"):
            response = post_batch(auth_client, [item])

        assert response.data["resultados"][0]["status"] == "conflito"
        conflito = ConflictLog.objects.get(campo="saude")
        assert conflito.campo_sensivel is True
        assert conflito.status == ConflictLog.Status.PENDENTE

        membro.refresh_from_db()
        assert membro.saude == ["asma"]  # LWW automático NÃO aplicado
