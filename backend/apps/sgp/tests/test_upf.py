import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import UPF

pytestmark = pytest.mark.django_db


class TestUPFCriacao:
    def test_create_upf_with_minimum_required_fields(
        self, auth_client, upf_payload_minimo
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["nome_titular"] == "Maria da Silva"
        assert response.data["ativa"] is True

    def test_create_upf_with_all_fields(
        self, auth_client, upf_payload_completo
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_completo, format="json"
        )
        assert response.status_code == 201
        assert response.data["rg"] == "1234567"
        assert response.data["email"] == "joao@example.com"
        assert response.data["latitude"] == "-5.123456"
        assert response.data["nome_mae"] == "Mãe do João"

    def test_cep_optional(self, auth_client, upf_payload_minimo):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["cep"] == ""


class TestValidacaoCPF:
    @pytest.mark.parametrize(
        "cpf_invalido",
        [
            "abc",
            "123",
            "12345678901",
        ],
    )
    def test_cpf_invalid_format_returns_400(
        self, auth_client, upf_payload_minimo, cpf_invalido
    ):
        payload = {**upf_payload_minimo, "cpf": cpf_invalido}
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 400

    def test_cpf_all_same_digits_returns_400(
        self, auth_client, upf_payload_minimo
    ):
        payload = {**upf_payload_minimo, "cpf": "11111111111"}
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 400


class TestUnicidadeCPF:
    def test_cpf_duplicate_same_projeto_returns_400(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 400
        assert "cpf" in response.data
        assert "Já existe uma UPF ativa" in str(response.data["cpf"])

    def test_cpf_duplicate_different_projetos_allowed(
        self, auth_client, upf_payload_minimo, outro_projeto
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        payload2 = {
            **upf_payload_minimo,
            "projeto": outro_projeto.pk,
        }
        response = auth_client.post(
            "/api/v1/upfs/", payload2, format="json"
        )
        assert response.status_code == 201

    def test_cpf_duplicate_but_inactive_allows_new_active(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]
        auth_client.delete(f"/api/v1/upfs/{upf_id}/")

        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201


class TestTerritorioAutomatico:
    def test_territorio_auto_filled_from_municipio(
        self, auth_client, upf_payload_minimo, municipio, territory
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["territorio"]["id"] == territory.pk

    def test_territorio_in_payload_is_ignored(
        self,
        auth_client,
        upf_payload_minimo,
        municipio,
        outro_territorio,
        territory,
    ):
        payload = {
            **upf_payload_minimo,
            "territorio": outro_territorio.pk,
        }
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 201
        upf = UPF.objects.get(pk=response.data["id"])
        assert upf.territorio_id == territory.pk
        assert upf.territorio_id != outro_territorio.pk


class TestSoftDelete:
    def test_soft_delete_sets_ativa_false_keeps_record(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.delete(f"/api/v1/upfs/{upf_id}/")
        assert response.status_code == 204

        upf = UPF.objects.get(pk=upf_id)
        assert upf.ativa is False


class TestSerializers:
    def test_list_serializer_returns_slim_payload(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200

        result = response.data["results"][0]
        expected_keys = {
            "id",
            "nome_titular",
            "cpf",
            "municipio",
            "territorio",
            "criado_em",
            "ativa",
        }
        assert set(result.keys()) == expected_keys

    def test_detail_serializer_returns_full_payload_with_membros_array(
        self, auth_client, upf_payload_completo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_completo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/")
        assert response.status_code == 200

        assert "membros" in response.data
        assert response.data["membros"] == []
        assert "cpf" in response.data
        assert "municipio" in response.data
        assert isinstance(response.data["municipio"], dict)
        assert "territorio" in response.data
        assert isinstance(response.data["territorio"], dict)

    def test_cpf_masked_in_list(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.get("/api/v1/upfs/")
        result = [
            u for u in response.data["results"] if u["id"] == upf_id
        ][0]
        assert "***" in result["cpf"]
        assert result["cpf"].count("*") == 6


class TestAuditLog:
    def test_audit_log_created_on_create_and_update(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        assert AuditLog.objects.filter(
            entidade="UPF",
            entidade_id=str(upf_id),
            acao="UPF.create",
        ).exists()

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome_titular": "Nome Atualizado"},
            format="json",
        )

        assert AuditLog.objects.filter(
            entidade="UPF",
            entidade_id=str(upf_id),
            acao="UPF.update",
        ).exists()
