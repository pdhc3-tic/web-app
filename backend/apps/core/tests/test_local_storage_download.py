import time
from urllib.parse import parse_qs, urlparse

import pytest
from rest_framework import serializers

from apps.core.storage.serializers import SignedMediaUrlsMixin
from apps.core.storage.r2 import LocalStorage

KEY = "atividades/1/fotos/abc.jpg"


@pytest.fixture
def storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGE_BACKEND = "local"
    s = LocalStorage()
    s.save_from_bytes(KEY, b"\xff\xd8foto")
    return s


@pytest.mark.django_db
def test_url_assinada_vira_x_accel_redirect(client, storage):
    response = client.get(storage.generate_presigned_get(KEY, 300))

    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/protected-media/{KEY}"
    assert response["Content-Type"] == "image/jpeg"
    assert response.content == b""


@pytest.mark.django_db
def test_em_debug_o_django_entrega_o_arquivo(client, storage, settings):
    settings.DEBUG = True
    response = client.get(storage.generate_presigned_get(KEY, 300))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"\xff\xd8foto"


@pytest.mark.django_db
def test_assinatura_adulterada_expirada_ou_de_upload_e_recusada(client, storage):
    url = storage.generate_presigned_get(KEY, 300)
    assert client.get(url[:-4] + "0000").status_code == 403

    expirada = storage.generate_presigned_get(KEY, -1)
    assert client.get(expirada).status_code == 403

    # Assinatura de PUT (outro payload) não abre leitura.
    put_qs = parse_qs(urlparse(storage.generate_presigned_put(KEY, "image/jpeg", 6)).query)
    forjada = f"/api/v1/storage/local-download/?key={KEY}&expires={put_qs['expires'][0]}&signature={put_qs['signature'][0]}"
    assert client.get(forjada).status_code == 403


@pytest.mark.django_db
def test_key_inexistente_ou_fora_da_midia(client, storage):
    assert client.get(storage.generate_presigned_get("nao/existe.jpg", 300)).status_code == 404
    assert client.get(storage.generate_presigned_get("../settings.py", 300)).status_code == 400


def test_sign_url_assina_so_midia_local_e_fica_estavel_na_hora(storage):
    assinada = storage.sign_url(f"/media/{KEY}")
    qs = parse_qs(urlparse(assinada).query)

    assert assinada.startswith("/api/v1/storage/local-download/?")
    assert qs["key"] == [KEY]
    assert 3600 <= int(qs["expires"][0]) - time.time() <= 7200
    assert storage.sign_url(f"/media/{KEY}") == assinada
    assert storage.sign_url("https://externo.example.com/foto.jpg") == "https://externo.example.com/foto.jpg"
    assert storage.sign_url("") == ""


def test_mixin_assina_so_os_campos_de_midia(storage):
    class FotoSerializer(SignedMediaUrlsMixin, serializers.Serializer):
        signed_media_url_fields = ("foto_url",)
        foto_url = serializers.CharField()
        legenda = serializers.CharField()

    data = FotoSerializer({"foto_url": f"/media/{KEY}", "legenda": f"/media/{KEY}"}).data
    assert data["foto_url"].startswith("/api/v1/storage/local-download/?")
    assert data["legenda"] == f"/media/{KEY}"
