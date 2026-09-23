from types import SimpleNamespace

import pytest
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


def make_request(*, path="/api/v1/sgd/demandas/", is_staff=False, pk=1):
    return SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False, is_staff=is_staff, pk=pk),
        auth=None,
        META={},
        path=path,
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
    user = SimpleNamespace(pk=10, is_authenticated=True, is_staff=False)
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


def test_session_context_sets_super_admin_for_staff_admin_session(monkeypatch):
    """Sessão do Django (não JWT) no Admin, de um staff — sem token pra
    extrair role/território, trata como acesso total pra RLS."""
    request = make_request(path="/admin/sgd/demand/", is_staff=True, pk=42)
    request.user.is_authenticated = True
    cursor = RecordingCursor()
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", lambda request: None)
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == [
        ("SET LOCAL app.current_user_id = %s;", ["42"]),
        ("SET LOCAL app.user_territorios = %s;", [""]),
        ("SET LOCAL app.user_role = %s;", ["super-admin"]),
    ]


def test_session_context_skips_staff_session_outside_admin_path(monkeypatch):
    """A sessão de staff só vale dentro de /admin/ — fora dali (ex.: a mesma
    aba do navegador batendo na API depois de logar no Admin), não deve
    ganhar acesso total pra RLS."""
    request = make_request(path="/api/v1/sgd/demandas/", is_staff=True)
    request.user.is_authenticated = True
    cursor = RecordingCursor()
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", lambda request: None)
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == []


def test_session_context_skips_non_staff_session_in_admin_path(monkeypatch):
    """Sessão autenticada mas sem is_staff (não deveria nem conseguir logar
    no Admin, mas a checagem não confia só nisso) não ganha SET LOCAL."""
    request = make_request(path="/admin/sgd/demand/", is_staff=False)
    request.user.is_authenticated = True
    cursor = RecordingCursor()
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", lambda request: None)
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == []


def test_session_context_jwt_takes_priority_over_staff_session(monkeypatch):
    """Um JWT válido nunca deve ser ignorado em favor do branch de sessão do
    Admin, mesmo que o usuário também seja staff."""
    request = make_request(path="/admin/sgd/demand/", is_staff=True)
    cursor = RecordingCursor()
    user = SimpleNamespace(pk=7, is_authenticated=True, is_staff=True)
    token = {"user_id": 7, "territorios": [], "role": "articulador-estadual"}
    middleware = SessionContextMiddleware(lambda request: "ok")

    monkeypatch.setattr(middleware.jwt_authentication, "authenticate", lambda request: (user, token))
    monkeypatch.setattr("apps.core.middleware.transaction.atomic", lambda: DummyContext())
    monkeypatch.setattr("apps.core.middleware.connection.cursor", lambda: cursor)

    assert middleware(request) == "ok"
    assert cursor.calls == [
        ("SET LOCAL app.current_user_id = %s;", ["7"]),
        ("SET LOCAL app.user_territorios = %s;", [""]),
        ("SET LOCAL app.user_role = %s;", ["articulador-estadual"]),
    ]


# ---------------------------------------------------------------------------
# Resolução de role/território a partir do banco — o JWT emitido hoje
# (setup/serializers.py:LoginSerializer) nunca carrega essas claims, então
# esse fallback é quem faz a política RLS funcionar de verdade em produção.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBuildSessionContextFallbackDoBanco:
    def test_resolve_role_ugp_sem_claim_no_token(self):
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug="ugp")
        user = UserFactory(profiles=[(role, None)])
        middleware = SessionContextMiddleware(lambda request: "ok")

        context = middleware._build_session_context({"user_id": user.pk}, user)

        assert context["role"] == "ugp"
        assert context["territorios"] == ""

    def test_resolve_role_e_territorio_do_articulador_sem_claim_no_token(self):
        from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory

        territorio = TerritoryFactory()
        role = RoleFactory(slug="articulador-estadual")
        user = UserFactory(profiles=[(role, territorio)])
        middleware = SessionContextMiddleware(lambda request: "ok")

        context = middleware._build_session_context({"user_id": user.pk}, user)

        assert context["role"] == "articulador-estadual"
        assert context["territorios"] == str(territorio.pk)

    def test_role_do_token_tem_prioridade_sobre_o_banco(self):
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug="ugp")
        user = UserFactory(profiles=[(role, None)])
        middleware = SessionContextMiddleware(lambda request: "ok")

        context = middleware._build_session_context({"user_id": user.pk, "role": "fgd"}, user)

        assert context["role"] == "fgd"

    def test_papel_sem_criterio_proprio_na_rls_resolve_vazio(self):
        """Um papel fora de _ROLES_RLS (ex.: "adt-acr") não precisa de
        resolução — a policy de sgd_demand não olha pro app.user_role nesse
        caso, só pro "vê as próprias" via solicitante_id."""
        from apps.core.tests.factories import RoleFactory, UserFactory

        role = RoleFactory(slug="adt-acr")
        user = UserFactory(profiles=[(role, None)])
        middleware = SessionContextMiddleware(lambda request: "ok")

        context = middleware._build_session_context({"user_id": user.pk}, user)

        assert context["role"] == ""
