from contextlib import nullcontext
import unittest
from unittest.mock import MagicMock, call, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.core.middleware import SessionContextMiddleware


class SessionContextMiddlewareTests(unittest.TestCase):
    @patch("apps.core.middleware.transaction.atomic")
    @patch("apps.core.middleware.connection.cursor")
    @patch("apps.core.middleware.JWTStatelessUserAuthentication.authenticate")
    def test_sets_local_session_variables_for_authenticated_request(
        self, mock_authenticate, mock_cursor, mock_atomic
    ):
        mock_atomic.return_value = nullcontext()
        request = RequestFactory().get("/api/v1/territorios/")
        request.user = AnonymousUser()

        authenticated_user = type("AuthenticatedUser", (), {"is_authenticated": True})()
        token_payload = {"user_id": 9, "territorios": [3, 5, 8], "role": "gestor"}
        mock_authenticate.return_value = (authenticated_user, token_payload)

        get_response = MagicMock(return_value="ok")
        middleware = SessionContextMiddleware(get_response)
        response = middleware(request)

        self.assertEqual(response, "ok")
        cursor = mock_cursor.return_value.__enter__.return_value
        cursor.execute.assert_has_calls(
            [
                call("SET LOCAL app.current_user_id = %s;", ["9"]),
                call("SET LOCAL app.user_territorios = %s;", ["3,5,8"]),
                call("SET LOCAL app.user_role = %s;", ["gestor"]),
            ]
        )
