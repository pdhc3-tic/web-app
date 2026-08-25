from datetime import date

import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import MembroFamilia, UPF

pytestmark = pytest.mark.django_db


class TestCriacaoMembro:
    def test_create_membro_with_minimum_fields(
        self, auth_client, upf, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["nome"] == "João Filho"
        assert response.data["parentesco"] == "filho"

    def test_create_membro_titular(
        self, auth_client, upf, titular_payload
    ):
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            titular_payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_second_titular_returns_400(
        self, auth_client, upf, titular_payload
    ):
        # UPF already has a titular from the factory; adding another must fail
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            titular_payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_membro_without_cpf_allowed(
        self, auth_client, upf, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["cpf"] == ""

    def test_create_membro_with_invalid_cpf_returns_400(
        self, auth_client, upf, membro_payload_minimo
    ):
        payload = {**membro_payload_minimo, "cpf": "11111111111"}
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_membro_for_inactive_upf_returns_400(
        self, auth_client, upf_inativa, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/upfs/{upf_inativa.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 400
        assert "UPF inativa" in str(response.data)


class TestIdade:
    def test_idade_calculated_from_data_nasc(
        self, auth_client, upf
    ):
        payload = {
            "nome": "Criança",
            "parentesco": "filho",
            "data_nasc": "2010-06-15",
        }
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        today = date.today()
        expected_age = today.year - 2010 - (
            (today.month, today.day) < (6, 15)
        )
        assert response.data["idade"] == expected_age


class TestListagem:
    def test_list_membros_returns_only_for_own_upf(
        self, auth_client, upf, outra_upf, membro, membro_outra_upf
    ):
        response = auth_client.get(
            f"/api/v1/upfs/{upf.pk}/membros/"
        )
        assert response.status_code == 200
        ids = [m["id"] for m in response.data["results"]]
        assert membro.pk in ids
        assert membro_outra_upf.pk not in ids

    def test_access_membro_from_wrong_upf_returns_404(
        self, auth_client, upf, outra_upf, membro, membro_outra_upf
    ):
        response = auth_client.get(
            f"/api/v1/upfs/{upf.pk}/membros/{membro_outra_upf.pk}/"
        )
        assert response.status_code == 404


class TestSaude:
    def test_saude_json_accepts_valid_array(
        self, auth_client, upf, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "saude": ["diabetes", "hipertensao"],
        }
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["saude"] == ["diabetes", "hipertensao"]

    def test_saude_json_rejects_invalid_value(
        self, auth_client, upf, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "saude": ["doenca_inexistente"],
        }
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400


class TestDeleteUPF:
    def test_delete_upf_does_not_delete_membros(
        self, auth_client, upf, membro
    ):
        auth_client.delete(f"/api/v1/upfs/{upf.pk}/")
        upf_atualizada = UPF.objects.get(pk=upf.pk)
        assert upf_atualizada.ativa is False
        assert MembroFamilia.objects.filter(
            upf=upf, pk=membro.pk
        ).exists()


class TestAuditLog:
    def test_audit_log_on_membro_create_update_delete(
        self, auth_client, upf, membro_payload_minimo
    ):
        res = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        membro_id = res.data["id"]
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.create",
        ).exists()

        auth_client.patch(
            f"/api/v1/upfs/{upf.pk}/membros/{membro_id}/",
            {"nome": "Nome Atualizado"},
            format="json",
        )
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.update",
        ).exists()

        auth_client.delete(
            f"/api/v1/upfs/{upf.pk}/membros/{membro_id}/"
        )
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.delete",
        ).exists()


class TestDeleteTitular:
    def test_delete_unico_titular_retorna_400(
        self, auth_client, upf
    ):
        membro = upf.titular
        response = auth_client.delete(
            f"/api/v1/upfs/{upf.pk}/membros/{membro.pk}/"
        )
        assert response.status_code == 400
        assert "único titular" in str(response.data).lower()

    def test_delete_titular_com_outros_membros_retorna_400(
        self, auth_client, upf, membro
    ):
        response = auth_client.delete(
            f"/api/v1/upfs/{upf.pk}/membros/{upf.titular.pk}/"
        )
        assert response.status_code == 400
        assert "titularidade" in str(response.data).lower()


class TestCPFUnicoGlobal:
    def test_cpf_duplicado_entre_upfs_diferentes_retorna_400(
        self, auth_client, upf, outra_upf, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "cpf": "12345678909",
        }
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201

        payload_outra = {
            "nome": "Membro Duplicado",
            "parentesco": "filho",
            "cpf": "12345678909",
        }
        response = auth_client.post(
            f"/api/v1/upfs/{outra_upf.pk}/membros/",
            payload_outra,
            format="json",
        )
        assert response.status_code == 400
        assert "já existe um membro" in str(response.data).lower()


class TestDataNascimentoFutura:
    def test_data_nascimento_futura_retorna_400(
        self, auth_client, upf
    ):
        payload = {
            "nome": "Membro Futuro",
            "parentesco": "filho",
            "data_nasc": "2030-01-01",
        }
        response = auth_client.post(
            f"/api/v1/upfs/{upf.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400
        assert "futura" in str(response.data).lower()


class TestResumoMembros:
    def test_resumo_retorna_totais_e_faixas_etarias(
        self, auth_client, upf, membro
    ):
        response = auth_client.get(
            f"/api/v1/upfs/{upf.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        assert response.data["total_membros"] >= 2
        assert "faixa_etaria" in response.data
        assert "genero" in response.data
        assert response.data["tem_titular"] is True

    def test_resumo_sem_titular_retorna_false(
        self, auth_client, upf, membro
    ):
        upf.titular = membro
        upf.save()
        MembroFamilia.objects.filter(
            upf=upf, parentesco="titular"
        ).exclude(pk=membro.pk).update(parentesco="filho")

        response = auth_client.get(
            f"/api/v1/upfs/{upf.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        assert response.data["tem_titular"] is False

    def test_resumo_nao_inclui_dados_individuais(
        self, auth_client, upf, membro
    ):
        response = auth_client.get(
            f"/api/v1/upfs/{upf.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        dados = response.data
        assert "saude" not in dados
        assert "cor_raca" not in dados
        assert "cpf" not in dados
