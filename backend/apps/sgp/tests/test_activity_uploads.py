"""
Testes para os endpoints de upload de fotos e documentos de atividades (Issue #125).

Cobertura:
    1. Upload de foto válida (JPG < 800 KB) → 201 com arquivo_url
    2. 11ª foto em uma atividade → 400
    3. Documento em formato não permitido (.docx) → 400
    4. Documento > 10 MB → 400
    5. Reordenação de fotos altera ordem e listagem reflete
    6. Integração BE-1: após 1 foto, PATCH status → concluido é aceito
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tests.factories import RoleFactory, StateFactory, TerritoryFactory, UserFactory, MunicipalityFactory
from apps.sgp.models.activity_photo import ActivityPhoto
from apps.sgp.models.activity_document import ActivityDocument
from apps.sgp.tests.factories import ActivityFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def territory(db):
    state = StateFactory(sigla="RN", nome="Rio Grande do Norte")
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def municipio(db, territory):
    state = StateFactory(sigla="RN", nome="Rio Grande do Norte")
    return MunicipalityFactory(
        nome="Mossoró",
        state=state,
        territory=territory,
        codigo_ibge="2408003",
    )


@pytest.fixture
def usuario_ugp(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="UGP User", profiles=[(role, None)])


@pytest.fixture
def auth_ugp(api_client, usuario_ugp):
    api_client.force_authenticate(user=usuario_ugp)
    return api_client


@pytest.fixture
def atividade(db, municipio):
    return ActivityFactory(municipio=municipio, status="em_andamento")


# Helpers de URL
def fotos_upload_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/fotos/upload-url/"


def fotos_confirm_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/fotos/confirm/"


def fotos_list_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/fotos/"


def fotos_delete_url(pk, foto_id):
    return f"/api/v1/sgp/atividades/{pk}/fotos/{foto_id}/"


def fotos_reordenar_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/fotos/reordenar/"


def docs_upload_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/documentos/upload-url/"


def docs_confirm_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/documentos/confirm/"


def docs_delete_url(pk, doc_id):
    return f"/api/v1/sgp/atividades/{pk}/documentos/{doc_id}/"


# ---------------------------------------------------------------------------
# Mock helpers — simula o storage R2
# ---------------------------------------------------------------------------

def _make_storage_mock(
    presigned_url="http://r2.example.com/upload",
    public_url="https://cdn.example.com/atividades/1/fotos/abc.jpg",
    head_content_length=102400,   # 100 KB
    head_content_type="image/jpeg",
    raise_not_found=False,
):
    """Cria um mock completo do storage backend."""
    mock = MagicMock()
    mock.generate_presigned_put.return_value = presigned_url
    mock.get_public_url.return_value = public_url
    if raise_not_found:
        from apps.core.storage import StorageObjectNotFound
        mock.head_object.side_effect = StorageObjectNotFound("key")
    else:
        mock.head_object.return_value = {
            "ContentLength": head_content_length,
            "ContentType": head_content_type,
        }
    mock.generate_presigned_get.return_value = "https://cdn.example.com/download"
    mock.delete_object.return_value = None
    return mock


# ===========================================================================
# Teste 1 — Upload de foto válida (JPG < 800 KB) → 201 com arquivo_url
# ===========================================================================

@pytest.mark.django_db
def test_upload_foto_valida_retorna_201(auth_ugp, atividade):
    """
    Fluxo completo: upload-url → confirm.
    Arquivo JPG de 100 KB deve ser aceito e retornar 201 com arquivo_url.
    """
    storage_mock = _make_storage_mock(
        presigned_url="http://r2.example.com/put",
        public_url="https://cdn.example.com/atividades/1/fotos/img.jpg",
        head_content_length=102_400,   # 100 KB — dentro do limite
        head_content_type="image/jpeg",
    )

    with patch("apps.sgp.views.activity_foto.get_storage", return_value=storage_mock):
        # Passo 1: obter URL presignada
        resp_url = auth_ugp.post(
            fotos_upload_url(atividade.pk),
            data={
                "filename": "foto.jpg",
                "content_type": "image/jpeg",
                "size": 102_400,
            },
            format="json",
        )
        assert resp_url.status_code == status.HTTP_200_OK, resp_url.data
        key = resp_url.data["key"]

        # Passo 2: confirmar upload
        resp_confirm = auth_ugp.post(
            fotos_confirm_url(atividade.pk),
            data={"key": key, "legenda": "Foto da visita"},
            format="json",
        )

    assert resp_confirm.status_code == status.HTTP_201_CREATED, resp_confirm.data
    assert "arquivo_url" in resp_confirm.data
    assert resp_confirm.data["arquivo_url"] == "https://cdn.example.com/atividades/1/fotos/img.jpg"

    # Verificar persistência no banco
    assert ActivityPhoto.objects.filter(activity=atividade, ativa=True).count() == 1


@pytest.mark.django_db
def test_upload_foto_excede_800kb_retorna_400(auth_ugp, atividade):
    """Arquivo > 800 KB declarado no upload-url deve ser rejeitado antes do presigned PUT."""
    storage_mock = _make_storage_mock()

    with patch("apps.sgp.views.activity_foto.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            fotos_upload_url(atividade.pk),
            data={
                "filename": "grande.jpg",
                "content_type": "image/jpeg",
                "size": 900_000,   # 900 KB — excede 800 KB
            },
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "800" in str(resp.data)


# ===========================================================================
# Teste 2 — 11ª foto em uma atividade → 400
# ===========================================================================

@pytest.mark.django_db
def test_upload_11a_foto_retorna_400(auth_ugp, atividade):
    """Após 10 fotos ativas, qualquer novo upload deve retornar 400."""
    # Criar 10 fotos diretamente no banco (sem passar pelo storage)
    for i in range(10):
        ActivityPhoto.objects.create(
            activity=atividade,
            arquivo_key=f"atividades/{atividade.pk}/fotos/foto{i:02d}.jpg",
            arquivo_url=f"https://cdn.example.com/foto{i:02d}.jpg",
            ordem=i,
            ativa=True,
        )

    assert ActivityPhoto.objects.filter(activity=atividade, ativa=True).count() == 10

    storage_mock = _make_storage_mock()
    with patch("apps.sgp.views.activity_foto.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            fotos_upload_url(atividade.pk),
            data={
                "filename": "extra.jpg",
                "content_type": "image/jpeg",
                "size": 50_000,
            },
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "10" in str(resp.data) or "Limite" in str(resp.data)


@pytest.mark.django_db
def test_confirm_11a_foto_retorna_400(auth_ugp, atividade):
    """Confirm também deve rejeitar se já existem 10 fotos ativas."""
    for i in range(10):
        ActivityPhoto.objects.create(
            activity=atividade,
            arquivo_key=f"atividades/{atividade.pk}/fotos/foto{i:02d}.jpg",
            arquivo_url=f"https://cdn.example.com/foto{i:02d}.jpg",
            ordem=i,
            ativa=True,
        )

    storage_mock = _make_storage_mock()
    fake_key = f"atividades/{atividade.pk}/fotos/aaaabbbb-cccc-dddd-eeee-000000000000.jpg"

    with patch("apps.sgp.views.activity_foto.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            fotos_confirm_url(atividade.pk),
            data={"key": fake_key},
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ===========================================================================
# Teste 3 — Documento em formato não permitido → 400
# ===========================================================================

@pytest.mark.django_db
def test_upload_documento_formato_invalido_retorna_400(auth_ugp, atividade):
    """Content-type application/vnd.openxmlformats (.docx) deve ser rejeitado."""
    storage_mock = _make_storage_mock()

    with patch("apps.sgp.views.activity_documentos.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            docs_upload_url(atividade.pk),
            data={
                "filename": "relatorio.docx",
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": 500_000,
            },
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "PDF" in str(resp.data) or "inválido" in str(resp.data).lower()


@pytest.mark.django_db
def test_upload_documento_pdf_valido_retorna_201(auth_ugp, atividade):
    """PDF dentro do limite deve resultar em 201."""
    storage_mock = _make_storage_mock(
        presigned_url="http://r2.example.com/put",
        public_url="https://cdn.example.com/atividades/1/documentos/doc.pdf",
        head_content_length=500_000,
        head_content_type="application/pdf",
    )

    with patch("apps.sgp.views.activity_documentos.get_storage", return_value=storage_mock):
        # Passo 1: upload-url
        resp_url = auth_ugp.post(
            docs_upload_url(atividade.pk),
            data={
                "filename": "lista_presenca.pdf",
                "content_type": "application/pdf",
                "size": 500_000,
            },
            format="json",
        )
        assert resp_url.status_code == status.HTTP_200_OK, resp_url.data
        key = resp_url.data["key"]

        # Passo 2: confirm
        resp_confirm = auth_ugp.post(
            docs_confirm_url(atividade.pk),
            data={
                "key": key,
                "tipo": "lista_presenca",
                "nome_original": "lista_presenca.pdf",
                "data_documento": "2026-08-01",
            },
            format="json",
        )

    assert resp_confirm.status_code == status.HTTP_201_CREATED, resp_confirm.data
    assert ActivityDocument.objects.filter(activity=atividade, ativo=True).count() == 1


# ===========================================================================
# Teste 4 — Documento > 10 MB → 400
# ===========================================================================

@pytest.mark.django_db
def test_upload_documento_maior_10mb_retorna_400(auth_ugp, atividade):
    """PDF com size declarado > 10 MB deve ser rejeitado no upload-url."""
    storage_mock = _make_storage_mock()

    with patch("apps.sgp.views.activity_documentos.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            docs_upload_url(atividade.pk),
            data={
                "filename": "enorme.pdf",
                "content_type": "application/pdf",
                "size": 11_000_000,   # 11 MB
            },
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "10" in str(resp.data)


@pytest.mark.django_db
def test_sexto_documento_retorna_400(auth_ugp, atividade):
    """6º documento deve retornar 400 (limite é 5)."""
    for i in range(5):
        ActivityDocument.objects.create(
            activity=atividade,
            arquivo_key=f"atividades/{atividade.pk}/documentos/doc{i}.pdf",
            arquivo_url=f"https://cdn.example.com/doc{i}.pdf",
            tipo="ata",
            nome_original=f"doc{i}.pdf",
            data_documento=datetime.date(2026, 8, 1),
            ativo=True,
        )

    storage_mock = _make_storage_mock()
    with patch("apps.sgp.views.activity_documentos.get_storage", return_value=storage_mock):
        resp = auth_ugp.post(
            docs_upload_url(atividade.pk),
            data={
                "filename": "extra.pdf",
                "content_type": "application/pdf",
                "size": 100_000,
            },
            format="json",
        )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "5" in str(resp.data) or "Limite" in str(resp.data)


# ===========================================================================
# Teste 5 — Reordenação de fotos
# ===========================================================================

@pytest.mark.django_db
def test_reordenacao_fotos_persiste_e_listagem_reflete(auth_ugp, atividade):
    """
    Criar 3 fotos com ordens 0, 1, 2.
    Reordenar enviando [foto3_id, foto1_id, foto2_id].
    Verificar que as ordens são 0, 1, 2 respectivamente após o PATCH.
    """
    foto_a = ActivityPhoto.objects.create(
        activity=atividade, arquivo_key="k/a.jpg",
        arquivo_url="https://cdn.example.com/a.jpg", ordem=0, ativa=True,
    )
    foto_b = ActivityPhoto.objects.create(
        activity=atividade, arquivo_key="k/b.jpg",
        arquivo_url="https://cdn.example.com/b.jpg", ordem=1, ativa=True,
    )
    foto_c = ActivityPhoto.objects.create(
        activity=atividade, arquivo_key="k/c.jpg",
        arquivo_url="https://cdn.example.com/c.jpg", ordem=2, ativa=True,
    )

    # Reordenar: C → A → B
    resp = auth_ugp.patch(
        fotos_reordenar_url(atividade.pk),
        data={"ids": [foto_c.pk, foto_a.pk, foto_b.pk]},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK, resp.data

    # Verificar no banco
    foto_a.refresh_from_db()
    foto_b.refresh_from_db()
    foto_c.refresh_from_db()

    assert foto_c.ordem == 0, "foto_c deve ser a capa (ordem=0)"
    assert foto_a.ordem == 1
    assert foto_b.ordem == 2

    # Verificar que a listagem reflete a nova ordem
    resp_list = auth_ugp.get(fotos_list_url(atividade.pk))
    assert resp_list.status_code == status.HTTP_200_OK
    ids_listados = [item["id"] for item in resp_list.data]
    assert ids_listados == [foto_c.pk, foto_a.pk, foto_b.pk]


@pytest.mark.django_db
def test_reordenacao_com_id_invalido_retorna_400(auth_ugp, atividade):
    """IDs de outra atividade ou inexistentes devem retornar 400."""
    foto = ActivityPhoto.objects.create(
        activity=atividade, arquivo_key="k/f.jpg",
        arquivo_url="https://cdn.example.com/f.jpg", ordem=0, ativa=True,
    )

    resp = auth_ugp.patch(
        fotos_reordenar_url(atividade.pk),
        data={"ids": [foto.pk, 99999]},  # 99999 não existe
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_soft_delete_foto(auth_ugp, atividade):
    """DELETE deve marcar ativa=False sem remover do banco."""
    foto = ActivityPhoto.objects.create(
        activity=atividade, arquivo_key="k/del.jpg",
        arquivo_url="https://cdn.example.com/del.jpg", ordem=0, ativa=True,
    )

    resp = auth_ugp.delete(fotos_delete_url(atividade.pk, foto.pk))
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    foto.refresh_from_db()
    assert foto.ativa is False  # soft-delete — objeto ainda existe
    assert ActivityPhoto.objects.filter(pk=foto.pk).exists()


# ===========================================================================
# Teste 6 — Integração BE-1: após 1 foto, PATCH status concluido é aceito
# ===========================================================================

@pytest.mark.django_db
def test_integracao_foto_permite_concluir_atividade(auth_ugp, atividade):
    """
    Com ao menos 1 foto ativa vinculada, o PATCH para status='concluido'
    deve ser aceito pelo serializer de Activity (has_evidencias() retorna True).
    """
    # A atividade já está em 'em_andamento' (fixture)
    assert atividade.status == "em_andamento"

    # Criar 1 foto diretamente (simula foto já confirmada)
    ActivityPhoto.objects.create(
        activity=atividade,
        arquivo_key=f"atividades/{atividade.pk}/fotos/capa.jpg",
        arquivo_url="https://cdn.example.com/capa.jpg",
        ordem=0,
        ativa=True,
    )

    # Verificar que has_evidencias() retorna True
    atividade.refresh_from_db()
    assert atividade.has_evidencias() is True

    # PATCH para concluido deve agora ser aceito
    resp = auth_ugp.patch(
        f"/api/v1/sgp/atividades/{atividade.pk}/",
        data={"status": "concluido"},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK, (
        f"Com evidência vinculada, status='concluido' deve ser aceito. Resposta: {resp.data}"
    )
    assert resp.data["status"] == "concluido"

    atividade.refresh_from_db()
    assert atividade.status == "concluido"


@pytest.mark.django_db
def test_integracao_sem_foto_nao_permite_concluir(auth_ugp, atividade):
    """Sem evidências, PATCH para concluido deve continuar retornando 400."""
    assert atividade.has_evidencias() is False

    resp = auth_ugp.patch(
        f"/api/v1/sgp/atividades/{atividade.pk}/",
        data={"status": "concluido"},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "evidência" in str(resp.data).lower() or "evidencia" in str(resp.data).lower()
