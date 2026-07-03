from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import UPF
from apps.sgp.tests.factories import UPFFactory

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
            {"nome_titular": "Maria Updated"},
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
            {"nome_titular": "Maria Updated"},
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
            {"nome_titular": "Updated", "email": "novo@email.com"},
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
            {"nome_titular": "Updated", "email": "novo@email.com"},
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

        now = timezone.now()
        desde = (now - timedelta(hours=1)).isoformat()
        ate = (now + timedelta(hours=1)).isoformat()

        response = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?desde={desde}&ate={ate}"
        )
        assert response.status_code == 200
        assert response.data["count"] == 1

        response_futuro = auth_client.get(
            f"/api/v1/upfs/{upf_id}/historico/?desde={(now + timedelta(hours=2)).isoformat()}"
        )
        assert response_futuro.status_code == 200
        assert response_futuro.data["count"] == 0


class TestHistoricoPaginacao:
    def test_historico_pagination_default_25(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post("/api/v1/upfs/", upf_payload_minimo, format="json")
        upf_id = res.data["id"]

        for i in range(26):
            auth_client.patch(
                f"/api/v1/upfs/{upf_id}/",
                {"nome_titular": f"Maria Updated {i}"},
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
            {"nome_titular": "Update 1"},
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
            cpf="52998224725",
        )
        response = auth_client_adt_rn.get(
            f"/api/v1/upfs/{upf_ce.pk}/historico/"
        )
        assert response.status_code == 404
