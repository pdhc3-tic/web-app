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
        assert log.valores_novos["saude_definido"] is True
        assert log.valores_novos["cor_raca_definido"] is True
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
        assert log.valores_novos["saude_alterado"] is True
        assert log.valores_novos["cor_raca_alterado"] is False
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
        assert log.valores_novos["saude_alterado"] is False
        assert log.valores_novos["cor_raca_alterado"] is False

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
        assert log.valores_anteriores["saude_definido"] is True
        assert log.valores_anteriores["cor_raca_definido"] is True
        assert "doenca_renal" not in str(log.valores_anteriores)
