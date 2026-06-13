"""
Testes unitários para apps/core/services/audit.py
"""
import pytest
from unittest.mock import MagicMock
from apps.core.services.audit import log_audit
from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import UserFactory


@pytest.mark.django_db
class TestLogAudit:
    def test_with_request_populates_ip_and_user_agent(self):
        """Quando request é fornecido, ip e user_agent são populados."""
        user = UserFactory()
        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.42",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_USER_AGENT": "TestAgent/1.0",
        }
        request.user = user

        log = log_audit(
            user=user,
            acao="organization_created",
            modulo="core",
            entidade="Organization",
            entidade_id=1,
            valores_novos={"nome": "Org Teste"},
            request=request,
        )

        assert log.ip == "203.0.113.42"
        assert log.user_agent == "TestAgent/1.0"

    def test_without_request_ip_is_none(self):
        """Sem request, ip e user_agent ficam None."""
        user = UserFactory()

        log = log_audit(
            user=user,
            acao="system_config_updated",
            modulo="core",
            entidade="SystemConfig",
            entidade_id=1,
        )

        assert log.ip is None
        assert log.user_agent == ""

    def test_unauthenticated_user_is_stored_as_none(self):
        """Usuário anônimo (is_authenticated=False) é gravado como NULL."""
        anon = MagicMock()
        anon.is_authenticated = False

        log = log_audit(
            user=anon,
            acao="password_reset_completed",
            modulo="core",
            entidade="User",
            entidade_id=99,
        )

        assert log.user is None

    def test_valores_default_to_empty_dict(self):
        """valores_anteriores e valores_novos default para {} quando omitidos."""
        user = UserFactory()

        log = log_audit(
            user=user,
            acao="organization_deleted",
            modulo="core",
            entidade="Organization",
            entidade_id=5,
        )

        assert log.valores_anteriores == {}
        assert log.valores_novos == {}

    def test_entidade_id_converted_to_str(self):
        """entidade_id é sempre gravado como string, independente do tipo recebido."""
        user = UserFactory()

        log = log_audit(
            user=user,
            acao="test_action",
            modulo="core",
            entidade="Model",
            entidade_id=42,
        )

        assert log.entidade_id == "42"
        assert isinstance(log.entidade_id, str)

    def test_override_ip_without_request(self):
        """_ip e _user_agent permitem passar contexto de thread sem request."""
        user = UserFactory()

        log = log_audit(
            user=user,
            acao="CREATE",
            modulo="core",
            entidade="Model",
            entidade_id=1,
            _ip="10.0.0.1",
            _user_agent="InternalAgent/2.0",
        )

        assert log.ip == "10.0.0.1"
        assert log.user_agent == "InternalAgent/2.0"
