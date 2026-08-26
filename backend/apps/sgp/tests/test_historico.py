import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import UPF
from apps.sgp.tests.factories import UPFFactory

FUTURE = "2099-01-01T00:00:00Z"
PAST = "2020-01-01T00:00:00Z"

pytestmark = pytest.mark.django_db

SENSITIVE_KEYWORDS = ["senha", "password", "token", "secret", "credential"]


class TestHistoricoCriacao:
    def test_historico_for_newly_created_upf_returns_only_create_event(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        assert response.status_code == 200
        assert response.data["count"] == 1
        entry = response.data["results"][0]
        assert entry["campo"] is None
        assert entry["valor_anterior"] is None
        assert entry["valor_novo"]["nome_titular"] == "Maria da Silva"


class TestHistoricoAtualizacoes:
    def test_historico_includes_subsequent_updates(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Maria Updated"},
            format="json",
        )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_historico_update_entry_has_correct_campo_anterior_novo(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Maria Updated"},
            format="json",
        )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        entries = response.data["results"]
        update_entries = [e for e in entries if e["campo"] == "nome_titular"]
        assert len(update_entries) == 1
        assert update_entries[0]["valor_anterior"] == "Maria da Silva"
        assert update_entries[0]["valor_novo"] == "Maria Updated"

    def test_historico_excludes_sensitive_fields(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Updated", "email": "novo@email.com"},
            format="json",
        )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        for entry in response.data["results"]:
            if entry["campo"] is not None:
                assert not any(kw in entry["campo"].lower() for kw in SENSITIVE_KEYWORDS)
            for val in (entry.get("valor_novo"), entry.get("valor_anterior")):
                if isinstance(val, dict):
                    for key in val:
                        assert not any(kw in key.lower() for kw in SENSITIVE_KEYWORDS)


class TestHistoricoFiltros:
    def test_historico_filter_by_campo(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Updated", "email": "novo@email.com"},
            format="json",
        )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/?campo=nome_titular")
        assert response.status_code == 200
        for entry in response.data["results"]:
            assert entry["campo"] == "nome_titular"

    def test_historico_filter_by_usuario(
        self, auth_client, upf_payload_minimo, usuario
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        response = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?usuario={usuario.pk}"
        )
        assert response.status_code == 200
        assert response.data["count"] >= 1

        response_empty = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?usuario=99999"
        )
        assert response_empty.status_code == 200
        assert response_empty.data["count"] == 0

    def test_historico_filter_by_date_range(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        response = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?desde={PAST}"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response_futuro = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?desde={FUTURE}"
        )
        assert response_futuro.status_code == 200
        assert response_futuro.data["count"] == 0

        response_past_ate = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?ate={PAST}"
        )
        assert response_past_ate.status_code == 200
        assert response_past_ate.data["count"] == 0


class TestHistoricoPaginacao:
    def test_historico_pagination_default_25(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        for i in range(26):
            auth_client.patch(
                f"/api/v1/upfs/{upf_id}/",
                {"nome": f"Maria Updated {i}"},
                format="json",
            )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 25
        assert response.data["count"] == 27

    def test_historico_ordering_timestamp_desc(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Update 1"},
            format="json",
        )

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/historico/")
        timestamps = [e["timestamp"] for e in response.data["results"]]
        assert timestamps == sorted(timestamps, reverse=True)


class TestHistoricoPermissao:
    def test_adt_accessing_historico_outside_territory_returns_404(
        self, auth_client_adt_rn, projeto, municipio_ce, territory_ce
    ):
        upf_ce = UPFFactory(
            projeto=projeto,
            municipio=municipio_ce,
            territorio=territory_ce,
            titular_cpf="52998224725",
        )
        response = auth_client_adt_rn.get(
            f"/api/v1/upfs/{upf_ce.pk}/historico/"
        )
        assert response.status_code == 404


class TestHistoricoIncluirMembros:
    def test_historico_with_incluir_membros_returns_member_events(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        payload_membro = {"nome": "Filho Teste", "parentesco": "filho"}
        auth_client.post(
            f"/api/v1/sgp/upfs/{upf_id}/membros/",
            payload_membro,
            format="json",
        )

        response_sem = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/"
        )
        assert response_sem.data["count"] == 1

        response_com = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?incluir_membros=true"
        )
        assert response_com.data["count"] == 2


class TestPerformanceIndexes:
    def test_query_uses_audit_log_index(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        for i in range(5):
            auth_client.patch(
                f"/api/v1/upfs/{upf_id}/",
                {"nome": f"Update {i}"},
                format="json",
            )

        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = OFF")
            qs = AuditLog.objects.filter(
                entidade="UPF", entidade_id=str(upf_id)
            )
            explain = qs.explain(analyze=True)
        assert "Index Scan" in explain or "Index Only Scan" in explain or "Bitmap Heap Scan" in explain
