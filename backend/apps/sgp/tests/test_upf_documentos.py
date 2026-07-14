import re

import pytest

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound
from apps.sgp.models import UPFDocument
from apps.sgp.tests.factories import UPFDocumentFactory, UPFFactory


pytestmark = pytest.mark.django_db


class FakeStorage:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.presigned_put_calls = []
        self.presigned_get_calls = []
        self.head_calls = []
        self.deleted_keys = []

    def generate_presigned_put(self, key, content_type, size, expires_in=300):
        self.presigned_put_calls.append((key, content_type, size, expires_in))
        return "https://upload.example.com/presigned"

    def generate_presigned_get(self, key, expires_in=300):
        self.presigned_get_calls.append((key, expires_in))
        return "https://download.example.com/presigned"

    def head_object(self, key):
        self.head_calls.append(key)
        if key not in self.objects:
            raise StorageObjectNotFound(key)
        return self.objects[key]

    def delete_object(self, key):
        self.deleted_keys.append(key)


def valid_upload_payload(**overrides):
    payload = {
        "filename": "documento.pdf",
        "content_type": "application/pdf",
        "size": 1024,
    }
    payload.update(overrides)
    return payload


def valid_create_payload(key, **overrides):
    payload = {
        "key": key,
        "nome_original": "documento.pdf",
        "tipo": "dap_caf",
        "descricao": "Documento DAP/CAF",
        "data_documento": "2026-01-15",
    }
    payload.update(overrides)
    return payload


def document_key(upf, ext="pdf"):
    return f"upfs/{upf.pk}/documentos/123e4567-e89b-12d3-a456-426614174000.{ext}"


def response_results(response):
    if isinstance(response.data, dict) and "results" in response.data:
        return response.data["results"]
    return response.data


def test_request_upload_url_for_document_returns_presigned(
    auth_client, upf, monkeypatch
):
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/upload-url/",
        valid_upload_payload(),
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data.keys()) == {"url", "key", "expires_in"}
    assert response.data["url"] == "https://upload.example.com/presigned"
    assert response.data["expires_in"] == 300
    assert re.match(
        rf"^upfs/{upf.pk}/documentos/[0-9a-f-]{{36}}\.pdf$",
        response.data["key"],
    )
    assert storage.presigned_put_calls == [
        (response.data["key"], "application/pdf", 1024, 300)
    ]


def test_request_upload_url_rejects_invalid_content_type(auth_client, upf):
    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/upload-url/",
        valid_upload_payload(content_type="application/zip"),
        format="json",
    )

    assert response.status_code == 400
    assert "Tipo de arquivo inválido" in str(response.data)


def test_request_upload_url_rejects_oversized(auth_client, upf):
    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/upload-url/",
        valid_upload_payload(size=15_728_640),
        format="json",
    )

    assert response.status_code == 400
    assert "tamanho máximo de 10 MB" in str(response.data)


def test_create_document_with_valid_key_persists_record(
    auth_client, upf, monkeypatch
):
    key = document_key(upf)
    storage = FakeStorage(
        objects={key: {"ContentLength": 2048, "ContentType": "application/pdf"}}
    )
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/",
        valid_create_payload(key),
        format="json",
    )

    assert response.status_code == 201
    document = UPFDocument.objects.get(pk=response.data["id"])
    assert document.upf == upf
    assert document.arquivo_key == key
    assert document.content_type == "application/pdf"
    assert document.tamanho_bytes == 2048
    assert storage.head_calls == [key]


def test_create_document_with_invalid_key_returns_400(auth_client, upf, monkeypatch):
    key = document_key(upf)
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/",
        valid_create_payload(key),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Upload não confirmado — tente novamente"
    assert not UPFDocument.objects.filter(arquivo_key=key).exists()


def test_list_documents_only_for_own_upf(auth_client, upf, outra_upf):
    own_document = UPFDocumentFactory(
        upf=upf,
        arquivo_key=document_key(upf),
    )
    UPFDocumentFactory(
        upf=outra_upf,
        arquivo_key=document_key(outra_upf),
    )

    response = auth_client.get(f"/api/v1/upfs/{upf.pk}/documentos/")

    assert response.status_code == 200
    ids = {item["id"] for item in response_results(response)}
    assert ids == {own_document.pk}


def test_cross_upf_document_returns_404(auth_client, upf, outra_upf):
    other_document = UPFDocumentFactory(
        upf=outra_upf,
        arquivo_key=document_key(outra_upf),
    )

    response = auth_client.get(
        f"/api/v1/upfs/{upf.pk}/documentos/{other_document.pk}/download/"
    )

    assert response.status_code == 404


def test_download_returns_presigned_get_url(auth_client, upf, monkeypatch):
    document = UPFDocumentFactory(upf=upf, arquivo_key=document_key(upf))
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.get(
        f"/api/v1/upfs/{upf.pk}/documentos/{document.pk}/download/"
    )

    assert response.status_code == 200
    assert response.data["url"] == "https://download.example.com/presigned"
    assert storage.presigned_get_calls == [(document.arquivo_key, 300)]


def test_download_url_expires_in_300_seconds(auth_client, upf, monkeypatch):
    document = UPFDocumentFactory(upf=upf, arquivo_key=document_key(upf))
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.get(
        f"/api/v1/upfs/{upf.pk}/documentos/{document.pk}/download/"
    )

    assert response.status_code == 200
    assert response.data["expires_in"] == 300
    assert storage.presigned_get_calls[0][1] == 300


def test_delete_document_calls_r2_and_removes_record(auth_client, upf, monkeypatch):
    document = UPFDocumentFactory(upf=upf, arquivo_key=document_key(upf))
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    response = auth_client.delete(
        f"/api/v1/upfs/{upf.pk}/documentos/{document.pk}/"
    )

    assert response.status_code == 204
    assert storage.deleted_keys == [document.arquivo_key]
    assert not UPFDocument.objects.filter(pk=document.pk).exists()


def test_adt_other_territory_cannot_access_documents(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        cpf="52998224725",
    )
    UPFDocumentFactory(upf=upf_ce, arquivo_key=document_key(upf_ce))

    response = auth_client_adt_rn.get(f"/api/v1/upfs/{upf_ce.pk}/documentos/")

    assert response.status_code == 404


def test_audit_log_on_document_operations(auth_client, upf, monkeypatch):
    key = document_key(upf)
    storage = FakeStorage(
        objects={key: {"ContentLength": 2048, "ContentType": "application/pdf"}}
    )
    monkeypatch.setattr("apps.sgp.views.upf_documentos.get_storage", lambda: storage)

    auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/upload-url/",
        valid_upload_payload(),
        format="json",
    )
    create_response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/documentos/",
        valid_create_payload(key),
        format="json",
    )
    document_id = create_response.data["id"]
    auth_client.get(f"/api/v1/upfs/{upf.pk}/documentos/{document_id}/download/")
    auth_client.delete(f"/api/v1/upfs/{upf.pk}/documentos/{document_id}/")

    for action in [
        "upload_document",
        "create_document",
        "download_document",
        "delete_document",
    ]:
        assert AuditLog.objects.filter(acao=action).exists()
