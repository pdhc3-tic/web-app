from types import SimpleNamespace

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.core.middleware import SessionContextMiddleware


class DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


def make_request():
    return SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False),
        auth=None,
        META={},
    )


def test_session_context_uses_jwt_authentication():
    middleware = SessionContextMiddleware(lambda request: "ok")

    assert isinstance(middleware.jwt_authentication, JWTAuthentication)


def test_session_context_skips_set_local_without_auth(monkeypatch):
    request = make_request()
    cursor = RecordingCursor()
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", lambda request: None)
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == []


def test_session_context_sets_local_for_authenticated_request(monkeypatch):
    request = make_request()
    cursor = RecordingCursor()
    user = SimpleNamespace(pk=10, is_authenticated=True)
    token = {
        "user_id": 10,
        "territorios": [1, 2],
        "role": "super-admin",
    }
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(
        middleware.jwt_authentication,
        "authenticate",
        lambda request: (user, token),
    )
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert request.user is user
    assert request.auth == token
    assert cursor.calls == [
        ("SET LOCAL app.current_user_id = %s;", ["10"]),
        ("SET LOCAL app.user_territorios = %s;", ["1,2"]),
        ("SET LOCAL app.user_role = %s;", ["super-admin"]),
    ]


def test_session_context_skips_set_local_when_jwt_is_invalid(monkeypatch):
    request = make_request()
    cursor = RecordingCursor()
    middleware = SessionContextMiddleware(lambda request: "ok")

    def raise_invalid_token(request):
        raise InvalidToken("invalid")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", raise_invalid_token)
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == []
