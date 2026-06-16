import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.factories import UserFactory
from apps.core.models.notifications import Notification, NotificationPreference


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def usuario():
    return UserFactory()


@pytest.fixture
def outro_usuario():
    return UserFactory()


def _auth(client, user):
    """Autentica o client com JWT do usuário."""
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


def _create_notification(user, **kwargs):
    """Helper para criar notificação."""
    defaults = {
        "user": user,
        "tipo": "in_app",
        "titulo": "Teste",
        "mensagem": "Mensagem de teste",
        "status": "pendente",
    }
    defaults.update(kwargs)
    return Notification.objects.create(**defaults)


# ──────────────────────────────────────────────────────────────
# 1. test_user_sees_only_own_notifications
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_user_sees_only_own_notifications(client, usuario, outro_usuario):
    notif_a = _create_notification(usuario, titulo="Para A")
    notif_b = _create_notification(outro_usuario, titulo="Para B")

    # Usuário A acessa /me/ — vê somente suas notificações
    _auth(client, usuario)
    response = client.get("/api/v1/notifications/me/")
    assert response.status_code == 200
    ids = [n["id"] for n in response.data["results"]]
    assert notif_a.pk in ids
    assert notif_b.pk not in ids

    # Usuário A tenta PATCH na notificação de B — 404, não 403
    response = client.patch(f"/api/v1/notifications/{notif_b.pk}/read/")
    assert response.status_code == 404


# ──────────────────────────────────────────────────────────────
# 2. test_mark_as_read_sets_lido_em
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_mark_as_read_sets_lido_em(client, usuario):
    notif = _create_notification(usuario)
    _auth(client, usuario)

    # Primeira chamada — marca como lida
    response = client.patch(f"/api/v1/notifications/{notif.pk}/read/")
    assert response.status_code == 200
    assert response.data["lido_em"] is not None
    primeiro_lido_em = response.data["lido_em"]

    # Segunda chamada — não altera o timestamp
    response = client.patch(f"/api/v1/notifications/{notif.pk}/read/")
    assert response.status_code == 200
    assert response.data["lido_em"] == primeiro_lido_em


# ──────────────────────────────────────────────────────────────
# 3. test_mark_all_read_updates_only_unread
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_mark_all_read_updates_only_unread(client, usuario):
    _create_notification(usuario)
    _create_notification(usuario)
    _create_notification(usuario, lido_em=timezone.now())  # já lida

    _auth(client, usuario)

    # Primeira chamada — atualiza 2 não-lidas
    response = client.post("/api/v1/notifications/mark-all-read/")
    assert response.status_code == 200
    assert response.data["updated_count"] == 2

    # Segunda chamada — nada para atualizar
    response = client.post("/api/v1/notifications/mark-all-read/")
    assert response.status_code == 200
    assert response.data["updated_count"] == 0


# ──────────────────────────────────────────────────────────────
# 4. test_unread_count_returns_correct_number
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_unread_count_returns_correct_number(client, usuario):
    _create_notification(usuario)  # não-lida
    _create_notification(usuario)  # não-lida
    _create_notification(usuario, lido_em=timezone.now())  # já lida

    _auth(client, usuario)
    response = client.get("/api/v1/notifications/me/unread-count/")
    assert response.status_code == 200
    assert response.data["count"] == 2


# ──────────────────────────────────────────────────────────────
# 5. test_unread_count_cache_invalidation
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_unread_count_cache_invalidation(client, usuario):
    _create_notification(usuario)  # 1 não-lida
    _auth(client, usuario)

    # Popula cache
    response = client.get("/api/v1/notifications/me/unread-count/")
    assert response.data["count"] == 1

    # Cria nova notificação — signal invalida cache
    _create_notification(usuario)

    # Count atualiza imediatamente
    response = client.get("/api/v1/notifications/me/unread-count/")
    assert response.data["count"] == 2


# ──────────────────────────────────────────────────────────────
# 6. test_pagination_default_page_size_20
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_pagination_default_page_size_20(client, usuario):
    for i in range(25):
        _create_notification(usuario, titulo=f"Notif {i}")

    _auth(client, usuario)
    response = client.get("/api/v1/notifications/me/")
    assert response.status_code == 200

    # LimitOffsetPagination retorna count, next, previous, results
    assert "count" in response.data
    assert "next" in response.data
    assert "previous" in response.data
    assert "results" in response.data
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20  # default_limit = 20


# ──────────────────────────────────────────────────────────────
# 7. test_ordering_default_recent_first
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_ordering_default_recent_first(client, usuario):
    n1 = _create_notification(usuario, titulo="Primeira")
    n2 = _create_notification(usuario, titulo="Segunda")
    n3 = _create_notification(usuario, titulo="Terceira")

    _auth(client, usuario)
    response = client.get("/api/v1/notifications/me/")
    assert response.status_code == 200

    ids = [n["id"] for n in response.data["results"]]
    # A mais recente (n3) deve vir primeiro
    assert ids == [n3.pk, n2.pk, n1.pk]


# ──────────────────────────────────────────────────────────────
# 8. test_notification_preference_uniqueness
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_notification_preference_uniqueness(usuario):
    NotificationPreference.objects.create(
        user=usuario,
        tipo_evento="nova_visita",
        canal="email",
    )

    with pytest.raises(IntegrityError):
        NotificationPreference.objects.create(
            user=usuario,
            tipo_evento="nova_visita",
            canal="email",
        )
