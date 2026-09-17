"""
Issue #187 — Proteção de campos sensíveis (Saúde, Cor/Raça).

Cobre: criptografia em repouso, matriz de permissão por perfil (6 perfis do
sistema) e registro no AuditLog sem vazar o valor do campo.
"""
import pytest
from django.db import connection

from apps.core.models.audit_log import AuditLog
from apps.core.sensitive_fields import SENSITIVE_FIELD_ROLES, sensitive_fields_visible_to
from apps.sgp.tests.factories import MembroFactory

pytestmark = pytest.mark.django_db

TODOS_OS_PERFIS = {
    "super-admin", "ugp", "articulador-estadual", "adt-acr", "fgd", "agricultor",
}


# ---------------------------------------------------------------------------
# Criptografia em repouso
# ---------------------------------------------------------------------------

class TestCriptografiaEmRepouso:
    def test_valor_bruto_no_banco_nao_e_legivel_em_texto_claro(self, upf):
        membro = MembroFactory(
            upf=upf,
            grau_parentesco="filho",
            cor_raca=3,
            saude=["diabetes", "gestante"],
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT cor_raca, saude FROM sgp_membrofamilia WHERE id = %s",
                [membro.pk],
            )
            raw_cor_raca, raw_saude = cursor.fetchone()

        # O valor persistido não pode ser o inteiro/lista original, nem
        # conter os termos em texto claro — a checagem é na camada de
        # persistência, não pela API.
        assert raw_cor_raca != "3"
        assert raw_saude is not None
        assert "diabetes" not in raw_saude
        assert "gestante" not in raw_saude

        # Mas o round-trip via ORM decripta corretamente.
        membro.refresh_from_db()
        assert membro.cor_raca == 3
        assert membro.saude == ["diabetes", "gestante"]

    def test_valores_nulos_e_vazios_sao_preservados(self, upf):
        membro = MembroFactory(upf=upf, grau_parentesco="filho", cor_raca=None, saude=[])
        membro.refresh_from_db()
        assert membro.cor_raca is None
        assert membro.saude == []

    def test_tokens_criptografados_sao_diferentes_para_o_mesmo_valor(self, upf):
        """Nonce aleatório por gravação: dois membros com o mesmo cor_raca não
        podem ter o mesmo texto cifrado (evita inferência por comparação)."""
        m1 = MembroFactory(upf=upf, grau_parentesco="filho", cor_raca=2)
        m2 = MembroFactory(upf=upf, grau_parentesco="conjuge", cor_raca=2)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT cor_raca FROM sgp_membrofamilia WHERE id IN (%s, %s)",
                [m1.pk, m2.pk],
            )
            valores = {row[0] for row in cursor.fetchall()}

        assert len(valores) == 2


# ---------------------------------------------------------------------------
# Matriz de permissão por perfil
# ---------------------------------------------------------------------------

class TestMatrizPermissaoCamposSensiveis:
    def test_matriz_cobre_todos_os_6_perfis_do_sistema(self):
        perfis_na_matriz = set()
        for roles in SENSITIVE_FIELD_ROLES.values():
            perfis_na_matriz |= roles
        assert perfis_na_matriz.issubset(TODOS_OS_PERFIS)

    @pytest.mark.parametrize(
        "perfil,esperado",
        [
            ("super-admin", {"saude", "cor_raca"}),
            ("ugp", {"saude", "cor_raca"}),
            ("articulador-estadual", {"saude", "cor_raca"}),
            ("adt-acr", {"saude", "cor_raca"}),
            ("fgd", set()),
            ("agricultor", set()),
        ],
    )
    def test_sensitive_fields_visible_to_para_cada_um_dos_6_perfis(
        self, perfil, esperado, request
    ):
        """Testa a função-fonte-única da matriz contra os 6 perfis do sistema."""
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug=perfil, nome=perfil)
        user = UserFactory(profiles=[(role, None)])
        assert sensitive_fields_visible_to(user) == esperado

    def test_usuario_anonimo_nao_ve_nenhum_campo_sensivel(self):
        assert sensitive_fields_visible_to(None) == set()

    def test_endpoint_detalhe_membro_perfil_com_permissao_ve_saude_e_cor_raca(
        self, auth_client_adt_rn, upf
    ):
        membro = MembroFactory(
            upf=upf, grau_parentesco="filho", cor_raca=1, saude=["hipertensao"]
        )
        response = auth_client_adt_rn.get(f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/")
        assert response.status_code == 200
        assert response.data["cor_raca"] == 1
        assert response.data["saude"] == ["hipertensao"]

    @pytest.mark.parametrize(
        "client_fixture",
        ["auth_client_super_admin", "auth_client_articulador_rn", "auth_client_adt_rn"],
    )
    def test_endpoint_detalhe_membro_perfis_autorizados_veem_campos_sensiveis(
        self, client_fixture, request, upf
    ):
        membro = MembroFactory(
            upf=upf, grau_parentesco="filho", cor_raca=1, saude=["hipertensao"]
        )
        client = request.getfixturevalue(client_fixture)
        response = client.get(f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/")
        assert response.status_code == 200
        assert "cor_raca" in response.data
        assert "saude" in response.data

    def test_endpoint_listagem_membro_perfil_sem_permissao_nao_ve_cor_raca(
        self, auth_client_fgd, upf
    ):
        """fgd hoje não tem acesso a nenhuma UPF (upfs_acessiveis_ao_usuario);
        a resposta correta é 404 — e por consequência nenhum campo (sensível
        ou não) é exposto a ele. Cobre o mesmo objetivo do critério de
        aceite (perfil sem permissão não recebe o campo)."""
        membro = MembroFactory(upf=upf, grau_parentesco="filho", cor_raca=1)
        response = auth_client_fgd.get(f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/")
        assert response.status_code == 404

    def test_campos_sensiveis_sao_omitidos_nunca_null_ou_mascarados(
        self, auth_client_adt_rn, upf
    ):
        """Confirma que, quando o campo é ocultado, ele some do payload —
        não aparece como None/"***" (o que sugeriria ao perfil sem permissão
        que o dado existe)."""
        from apps.core.sensitive_fields import SensitiveFieldsSerializerMixin
        from apps.sgp.serializers import MembroDetailSerializer

        assert issubclass(MembroDetailSerializer, SensitiveFieldsSerializerMixin)

        membro = MembroFactory(upf=upf, grau_parentesco="filho", cor_raca=1, saude=["gestante"])

        class _AnonRequest:
            user = None

        serializer = MembroDetailSerializer(membro, context={"request": _AnonRequest()})
        data = serializer.data
        assert "cor_raca" not in data
        assert "cor_raca_display" not in data
        assert "saude" not in data

    def test_titular_nested_serializer_tambem_respeita_a_matriz(self, upf):
        """TitularNestedSerializer (UPFDetailSerializer.titular) é a terceira
        superfície que expunha cor_raca sem filtro — cobre a correção."""
        from apps.core.sensitive_fields import SensitiveFieldsSerializerMixin
        from apps.sgp.serializers import TitularNestedSerializer

        assert issubclass(TitularNestedSerializer, SensitiveFieldsSerializerMixin)
        upf.titular.cor_raca = 4
        upf.titular.save(update_fields=["cor_raca"])
        titular = type(upf.titular).objects.get(pk=upf.titular_id)

        class _AnonRequest:
            user = None

        serializer = TitularNestedSerializer(titular, context={"request": _AnonRequest()})
        data = serializer.data
        assert "cor_raca" not in data
        assert "cor_raca_display" not in data

    def test_upf_detalhe_via_endpoint_nao_vaza_cor_raca_do_titular_sem_permissao(
        self, auth_client_fgd, upf
    ):
        response = auth_client_fgd.get(f"/api/v1/upfs/{upf.pk}/")
        # UPFViewSet nega perfis fora de super-admin/ugp/articulador-estadual/
        # adt-acr com 403 antes mesmo de resolver o objeto — nada vaza.
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Bloqueio de escrita de campos sensíveis por quem não tem permissão de leitura
#
# Correção de auditoria: a omissão na LEITURA já existia, mas um payload
# manual de criação/edição com saude/cor_raca era apenas ignorado em
# silêncio (a chave some de `self.fields` para quem não tem permissão, então
# o DRF não via o valor — sem erro nenhum). Hoje nenhum dos 6 perfis do RBAC
# tem acesso a UPF sem também ter acesso aos campos sensíveis (fgd/agricultor
# não acessam UPF nenhuma — ver `upfs_acessiveis_ao_usuario`), então o
# cenário não é reproduzível via HTTP; a cobertura é no nível do serializer,
# mesmo padrão já usado acima para a omissão de leitura.
# ---------------------------------------------------------------------------

class TestBloqueioDeEscritaCamposSensiveis:
    class _FakeRequest:
        def __init__(self, user):
            self.user = user

    def _usuario_sem_permissao(self):
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug="agricultor", nome="Agricultor")
        return UserFactory(profiles=[(role, None)])

    def _usuario_autorizado(self):
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug="adt-acr", nome="ADT")
        return UserFactory(profiles=[(role, None)])

    def test_criacao_com_cor_raca_por_usuario_sem_permissao_e_rejeitada(self):
        from apps.sgp.serializers import MembroDetailSerializer

        payload = {"nome_completo": "Novo Membro", "grau_parentesco": "filho", "cor_raca": 2}
        serializer = MembroDetailSerializer(
            data=payload,
            context={"request": self._FakeRequest(self._usuario_sem_permissao())},
        )

        assert not serializer.is_valid()
        assert "cor_raca" in serializer.errors

    def test_criacao_com_saude_por_usuario_sem_permissao_e_rejeitada(self):
        from apps.sgp.serializers import MembroDetailSerializer

        payload = {
            "nome_completo": "Novo Membro",
            "grau_parentesco": "filho",
            "saude": ["diabetes"],
        }
        serializer = MembroDetailSerializer(
            data=payload,
            context={"request": self._FakeRequest(self._usuario_sem_permissao())},
        )

        assert not serializer.is_valid()
        assert "saude" in serializer.errors

    def test_edicao_com_saude_por_usuario_sem_permissao_e_rejeitada(self, upf):
        from apps.sgp.serializers import MembroDetailSerializer

        membro = MembroFactory(upf=upf, grau_parentesco="filho", saude=[])
        serializer = MembroDetailSerializer(
            membro,
            data={"saude": ["hipertensao"]},
            partial=True,
            context={"request": self._FakeRequest(self._usuario_sem_permissao())},
        )

        assert not serializer.is_valid()
        assert "saude" in serializer.errors
        membro.refresh_from_db()
        assert membro.saude == []

    def test_erro_nao_expoe_o_valor_enviado_nem_descarta_em_silencio(self):
        """A rejeição é explícita (400 nos testes de view; aqui, erro de
        validação do serializer) — nunca um `is_valid()` silenciosamente
        `True` que descartaria o valor sem avisar quem fez a requisição."""
        from apps.sgp.serializers import MembroDetailSerializer

        payload = {
            "nome_completo": "Novo Membro",
            "grau_parentesco": "filho",
            "cor_raca": 5,
        }
        serializer = MembroDetailSerializer(
            data=payload,
            context={"request": self._FakeRequest(self._usuario_sem_permissao())},
        )

        assert not serializer.is_valid()
        assert "5" not in str(serializer.errors)

    def test_payload_sem_campos_sensiveis_nao_e_afetado(self):
        """Perfil sem permissão continua criando/editando membros normalmente
        — o bloqueio é só sobre saude/cor_raca."""
        from apps.sgp.serializers import MembroDetailSerializer

        payload = {"nome_completo": "Novo Membro", "grau_parentesco": "filho"}
        serializer = MembroDetailSerializer(
            data=payload,
            context={"request": self._FakeRequest(self._usuario_sem_permissao())},
        )

        assert serializer.is_valid(), serializer.errors

    def test_usuario_autorizado_nao_e_afetado_pelo_bloqueio(self):
        """Regressão: perfil com permissão de leitura (adt-acr) continua
        escrevendo saude/cor_raca normalmente."""
        from apps.sgp.serializers import MembroDetailSerializer

        payload = {
            "nome_completo": "Novo Membro",
            "grau_parentesco": "filho",
            "cor_raca": 2,
            "saude": ["diabetes"],
        }
        serializer = MembroDetailSerializer(
            data=payload,
            context={"request": self._FakeRequest(self._usuario_autorizado())},
        )

        assert serializer.is_valid(), serializer.errors


# ---------------------------------------------------------------------------
# AuditLog — sem vazar o valor
# ---------------------------------------------------------------------------

class TestAuditLogCamposSensiveis:
    def test_criacao_de_membro_registra_presenca_sem_expor_valor(self, auth_client_adt_rn, upf):
        payload = {
            "nome_completo": "Novo Membro",
            "grau_parentesco": "filho",
            "cor_raca": 2,
            "saude": ["diabetes"],
        }
        response = auth_client_adt_rn.post(
            f"/api/v1/sgp/upfs/{upf.pk}/membros/", payload, format="json"
        )
        assert response.status_code == 201

        log = AuditLog.objects.filter(acao="MEMBRO.create", entidade="MembroFamilia").latest(
            "timestamp"
        )
        assert set(log.valores_novos["campos_alterados"]) == {"saude", "cor_raca"}
        assert "diabetes" not in str(log.valores_novos)
        assert "cor_raca" not in log.valores_novos
        assert "saude" not in log.valores_novos

    def test_edicao_de_saude_gera_auditlog_com_usuario_campo_e_timestamp_sem_valor(
        self, auth_client_adt_rn, usuario_adt_rn, upf
    ):
        membro = MembroFactory(upf=upf, grau_parentesco="filho", saude=[])

        response = auth_client_adt_rn.patch(
            f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/",
            {"saude": ["hipertensao", "gestante"]},
            format="json",
        )
        assert response.status_code == 200

        log = AuditLog.objects.filter(
            acao="MEMBRO.update", entidade="MembroFamilia", entidade_id=str(membro.pk)
        ).latest("timestamp")

        assert log.user_id == usuario_adt_rn.pk
        assert log.timestamp is not None
        assert log.valores_novos["campos_alterados"] == ["saude"]
        assert "hipertensao" not in str(log.valores_novos)
        assert "gestante" not in str(log.valores_novos)
        assert "hipertensao" not in str(log.valores_anteriores)

    def test_edicao_sem_tocar_em_campo_sensivel_nao_marca_alterado(
        self, auth_client_adt_rn, upf
    ):
        membro = MembroFactory(upf=upf, grau_parentesco="filho", cor_raca=1, saude=["diabetes"])

        response = auth_client_adt_rn.patch(
            f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/",
            {"nome_completo": "Nome Atualizado"},
            format="json",
        )
        assert response.status_code == 200

        log = AuditLog.objects.filter(
            acao="MEMBRO.update", entidade="MembroFamilia", entidade_id=str(membro.pk)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == []

    def test_exclusao_de_membro_registra_presenca_sem_expor_valor(
        self, auth_client_adt_rn, upf
    ):
        outro_titular = MembroFactory(upf=upf, grau_parentesco="conjuge")
        membro = MembroFactory(
            upf=upf, grau_parentesco="filho", cor_raca=5, saude=["doenca_renal"]
        )

        response = auth_client_adt_rn.delete(
            f"/api/v1/sgp/upfs/{upf.pk}/membros/{membro.pk}/"
        )
        assert response.status_code == 204

        log = AuditLog.objects.filter(
            acao="MEMBRO.delete", entidade="MembroFamilia", entidade_id=str(membro.pk)
        ).latest("timestamp")
        assert set(log.valores_novos["campos_alterados"]) == {"saude", "cor_raca"}
        assert "doenca_renal" not in str(log.valores_novos)
        assert "doenca_renal" not in str(log.valores_anteriores)


# ---------------------------------------------------------------------------
# UPFDetailSerializer — cor_raca do titular escrita pela API de UPF
# ---------------------------------------------------------------------------

class TestUPFEscritaEAuditoriaDaCorRacaDoTitular:
    def test_cor_raca_do_titular_por_usuario_sem_permissao_e_rejeitada(self):
        from apps.core.tests.factories import RoleFactory, UserFactory
        from apps.sgp.serializers import UPFDetailSerializer

        role = RoleFactory(slug="agricultor", nome="Agricultor")
        user = UserFactory(profiles=[(role, None)])

        class _FakeRequest:
            def __init__(self, user):
                self.user = user

        payload = {
            "projeto": 1, "nome": "Novo Titular", "cpf": "86288366757",
            "municipio": 1, "cor_raca": 2,
        }
        serializer = UPFDetailSerializer(data=payload, context={"request": _FakeRequest(user)})

        assert not serializer.is_valid()
        assert "cor_raca" in serializer.errors

    def test_criacao_de_upf_audita_cor_raca_do_titular_como_membrofamilia(
        self, auth_client_adt_rn, projeto, municipio_rn
    ):
        payload = {
            "projeto": projeto.pk,
            "nome": "Titular Auditado",
            "cpf": "86288366757",
            "municipio": municipio_rn.pk,
            "cor_raca": 3,
        }
        response = auth_client_adt_rn.post("/api/v1/upfs/", payload, format="json")
        assert response.status_code == 201, response.data

        titular_id = response.data["titular"]["id"]
        log = AuditLog.objects.filter(
            acao="MEMBRO.create", entidade="MembroFamilia", entidade_id=str(titular_id)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == ["cor_raca"]
        assert "cor_raca" not in log.valores_novos
        assert log.valores_novos["origem"] == "web"

    def test_edicao_de_upf_altera_cor_raca_do_titular_e_audita_sem_valor(
        self, auth_client_adt_rn, upf
    ):
        titular_id = upf.titular_id
        response = auth_client_adt_rn.patch(
            f"/api/v1/upfs/{upf.pk}/", {"cor_raca": 4}, format="json"
        )
        assert response.status_code == 200

        upf.titular.refresh_from_db()
        assert upf.titular.cor_raca == 4

        log = AuditLog.objects.filter(
            acao="MEMBRO.update", entidade="MembroFamilia", entidade_id=str(titular_id)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == ["cor_raca"]
        assert "cor_raca" not in log.valores_novos


# ---------------------------------------------------------------------------
# saude na listagem — antes só cor_raca respeitava a matriz (Issue #187/#192)
# ---------------------------------------------------------------------------

class TestSaudeNaListagemDeMembros:
    def test_perfil_autorizado_recebe_saude_na_listagem(self, auth_client_adt_rn, upf):
        MembroFactory(upf=upf, grau_parentesco="filho", saude=["asma"])
        response = auth_client_adt_rn.get(f"/api/v1/sgp/upfs/{upf.pk}/membros/")
        assert response.status_code == 200
        item = next(m for m in response.data["results"] if m["grau_parentesco"] == "filho")
        assert item["saude"] == ["asma"]

    def test_campo_saude_omitido_da_listagem_e_omitido_nunca_null(self, upf):
        from apps.sgp.serializers import MembroListSerializer

        membro = MembroFactory(upf=upf, grau_parentesco="filho", saude=["asma"])

        class _AnonRequest:
            user = None

        serializer = MembroListSerializer(membro, context={"request": _AnonRequest()})
        assert "saude" not in serializer.data
