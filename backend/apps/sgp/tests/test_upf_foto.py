import re
import sys
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from django.test import override_settings

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound
from apps.sgp.models import UPF
from apps.sgp.tests.factories import UPFFactory


pytestmark = pytest.mark.django_db


class FakeStorage:
    public_url = "https://media.example.com"

    def __init__(self, existing_keys=None):
        self.existing_keys = set(existing_keys or [])
        self.presigned_calls = []
        self.head_calls = []
        self.deleted_keys = []

    def generate_presigned_put(self, key, content_type, size, expires_in=300):
        self.presigned_calls.append((key, content_type, size, expires_in))
        return "https://upload.example.com/presigned"

    def head_object(self, key):
        self.head_calls.append(key)
        if key not in self.existing_keys:
            raise StorageObjectNotFound(key)
        return {"ContentLength": 10}

    def delete_object(self, key):
        self.deleted_keys.append(key)

    def get_public_url(self, key):
        return f"{self.public_url}/{key}"

    def get_key_from_url(self, url):
        prefix = f"{self.public_url}/"
        if url and url.startswith(prefix):
            return url[len(prefix):]
        return ""


def valid_upload_payload(**overrides):
    payload = {
        "filename": "foto.png",
        "content_type": "image/png",
        "size": 1024,
    }
    payload.update(overrides)
    return payload


def photo_key(upf, ext="png"):
    return f"upfs/{upf.pk}/foto/123e4567-e89b-12d3-a456-426614174000.{ext}"


@override_settings(
    STORAGE_BACKEND="r2",
    R2_ACCESS_KEY_ID="access",
    R2_SECRET_ACCESS_KEY="secret",
    R2_BUCKET_NAME="pdhc-iii",
    R2_ENDPOINT_URL="https://account.r2.cloudflarestorage.com",
    R2_PUBLIC_URL="https://media.pdhc-iii.org",
)
def test_request_upload_url_returns_presigned_with_correct_fields(
    auth_client, upf, monkeypatch
):
    calls = {}

    class FakeS3Client:
        def generate_presigned_url(self, **kwargs):
            calls.update(kwargs)
            return "https://r2.example.com/presigned"

    fake_client = FakeS3Client()
    fake_boto3 = SimpleNamespace(client=lambda *args, **kwargs: fake_client)
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(),
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data.keys()) == {"url", "key", "expires_in"}
    assert response.data["url"] == "https://r2.example.com/presigned"
    assert response.data["expires_in"] == 300
    assert calls["ClientMethod"] == "put_object"
    assert calls["HttpMethod"] == "PUT"
    assert calls["ExpiresIn"] == 300
    assert calls["Params"]["Bucket"] == "pdhc-iii"
    assert calls["Params"]["Key"] == response.data["key"]
    assert calls["Params"]["ContentType"] == "image/png"
    assert calls["Params"]["ContentLength"] == 1024


def test_request_upload_url_rejects_invalid_content_type(auth_client, upf):
    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(content_type="image/gif"),
        format="json",
    )

    assert response.status_code == 400
    assert "Tipo de arquivo inválido" in str(response.data)


def test_request_upload_url_rejects_oversized(auth_client, upf):
    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(size=10_485_760),
        format="json",
    )

    assert response.status_code == 400
    assert "tamanho máximo de 5 MB" in str(response.data)


def test_request_upload_url_generates_unique_key(auth_client, upf, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    first = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(),
        format="json",
    )
    second = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(),
        format="json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data["key"] != second.data["key"]


def test_request_upload_url_key_format_matches_pattern(auth_client, upf, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(content_type="image/jpeg"),
        format="json",
    )

    assert response.status_code == 200
    assert re.match(
        rf"^upfs/{upf.pk}/foto/[0-9a-f-]{{36}}\.jpg$",
        response.data["key"],
    )


def test_request_upload_url_requires_permission(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        cpf="52998224725",
    )

    response = auth_client_adt_rn.post(
        f"/api/v1/upfs/{upf_ce.pk}/foto/upload-url/",
        valid_upload_payload(),
        format="json",
    )

    assert response.status_code == 404


def test_confirm_upload_calls_head_object(auth_client, upf, monkeypatch):
    key = photo_key(upf)
    storage = FakeStorage(existing_keys={key})
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": key},
        format="json",
    )

    assert response.status_code == 200
    assert storage.head_calls == [key]


def test_confirm_upload_updates_foto_url(auth_client, upf, monkeypatch):
    key = photo_key(upf)
    storage = FakeStorage(existing_keys={key})
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": key},
        format="json",
    )

    assert response.status_code == 200
    upf.refresh_from_db()
    assert upf.foto_url == f"https://media.example.com/{key}"


def test_confirm_upload_fails_if_object_not_found(auth_client, upf, monkeypatch):
    key = photo_key(upf)
    storage = FakeStorage()
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": key},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Upload não confirmado — tente novamente"


def test_confirm_upload_deletes_previous_photo(auth_client, upf, monkeypatch):
    old_key = photo_key(upf, ext="jpg")
    new_key = photo_key(upf, ext="png")
    upf.foto_url = f"https://media.example.com/{old_key}"
    upf.save(update_fields=["foto_url"])
    storage = FakeStorage(existing_keys={new_key})
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": new_key},
        format="json",
    )

    assert response.status_code == 200
    assert old_key in storage.deleted_keys


def test_delete_photo_calls_delete_object_and_clears_field(
    auth_client, upf, monkeypatch
):
    key = photo_key(upf)
    upf.foto_url = f"https://media.example.com/{key}"
    upf.save(update_fields=["foto_url"])
    storage = FakeStorage(existing_keys={key})
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    response = auth_client.delete(f"/api/v1/upfs/{upf.pk}/foto/")

    assert response.status_code == 204
    assert storage.deleted_keys == [key]
    upf.refresh_from_db()
    assert upf.foto_url == ""


def test_audit_log_entries_created_for_photo_operations(
    auth_client, upf, monkeypatch
):
    key = photo_key(upf)
    storage = FakeStorage(existing_keys={key})
    monkeypatch.setattr("apps.sgp.views.upf_foto.get_storage", lambda: storage)

    auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(),
        format="json",
    )
    auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": key},
        format="json",
    )
    auth_client.delete(f"/api/v1/upfs/{upf.pk}/foto/")

    for action in ["upload_photo", "confirm_photo", "delete_photo"]:
        assert AuditLog.objects.filter(
            entidade="UPF",
            entidade_id=str(upf.pk),
            acao=action,
        ).exists()


def test_local_backend_path_storage(auth_client, upf, settings, tmp_path):
    settings.STORAGE_BACKEND = "local"
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    content = b"fake-image"

    upload_response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(size=len(content)),
        format="json",
    )
    assert upload_response.status_code == 200

    parsed = urlparse(upload_response.data["url"])
    put_response = auth_client.put(
        f"{parsed.path}?{parsed.query}",
        data=content,
        content_type="image/png",
    )
    assert put_response.status_code == 200

    key = upload_response.data["key"]
    assert (tmp_path / key).read_bytes() == content

    confirm_response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/confirm/",
        {"key": key},
        format="json",
    )
    assert confirm_response.status_code == 200
    assert UPF.objects.get(pk=upf.pk).foto_url == f"/media/{key}"


def test_local_upload_rejects_body_larger_than_signed_size(
    auth_client, upf, settings, tmp_path
):
    settings.STORAGE_BACKEND = "local"
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    content = b"fake-image"

    upload_response = auth_client.post(
        f"/api/v1/upfs/{upf.pk}/foto/upload-url/",
        valid_upload_payload(size=len(content) - 1),
        format="json",
    )
    assert upload_response.status_code == 200

    parsed = urlparse(upload_response.data["url"])
    put_response = auth_client.put(
        f"{parsed.path}?{parsed.query}",
        data=content,
        content_type="image/png",
    )

    assert put_response.status_code == 400
    assert put_response.data["detail"] == "Arquivo excede o tamanho autorizado."
    assert not (tmp_path / upload_response.data["key"]).exists()
