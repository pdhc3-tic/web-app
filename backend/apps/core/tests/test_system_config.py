import pytest
from django.core.cache import cache
from rest_framework import status

from apps.core.models.audit_log import AuditLog
from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.utils import get_config

pytestmark = pytest.mark.django_db

SEED_KEYS = [
    "session_timeout_hours",
    "max_login_attempts",
    "lockout_minutes",
    "notification_demand_alert_days",
    "notification_form_deadline_days",
    "user_inactive_alert_days",
    "backup_retention_days",
    "sca_sync_batch_limit",
    "report_export_row_limit",
]


class TestSeeds:
    """Tests for data migration seeds (0012_seed_system_config)."""

    def test_seeds_create_all_default_parameters(self):
        assert SystemConfig.objects.count() >= 9
        for chave in SEED_KEYS:
            assert SystemConfig.objects.filter(chave=chave).exists()


class TestGetConfig:
    def test_get_config_returns_typed_value(self):
        cache.clear()
        SystemConfig.objects.create(
            chave="test_max_login_attempts",
            valor="5",
            tipo=TipoConfiguracao.INTEGER,
        )
        result = get_config("test_max_login_attempts")
        assert isinstance(result, int)
        assert result == 5

    def test_get_config_caches_result(self, django_assert_num_queries):
        cache.clear()
        SystemConfig.objects.create(
            chave="test_cache_config",
            valor="5",
            tipo=TipoConfiguracao.INTEGER,
        )

        with django_assert_num_queries(1):
            result = get_config("test_cache_config")
        assert result == 5

        with django_assert_num_queries(0):
            result2 = get_config("test_cache_config")
        assert result2 == 5

    def test_get_config_cache_invalidated_on_save(self):
        cache.clear()
        config = SystemConfig.objects.create(
            chave="test_cache_invalidation",
            valor="5",
            tipo=TipoConfiguracao.INTEGER,
        )

        get_config("test_cache_invalidation")

        config.valor = "10"
        config.save()

        result = get_config("test_cache_invalidation")
        assert result == 10


class TestAPI:
    @pytest.fixture
    def config_int(self, db):
        return SystemConfig.objects.create(
            chave="test_integer_param",
            valor="42",
            tipo=TipoConfiguracao.INTEGER,
            descricao="Test integer parameter",
        )

    def test_only_super_admin_can_patch(
        self, api_client, config_int, super_admin_user, ugp_user
    ):
        api_client.force_authenticate(user=ugp_user)
        response = api_client.patch(
            f"/api/v1/system-config/{config_int.chave}/", {"valor": "99"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        api_client.force_authenticate(user=super_admin_user)
        response = api_client.patch(
            f"/api/v1/system-config/{config_int.chave}/", {"valor": "99"}
        )
        assert response.status_code == status.HTTP_200_OK
        config_int.refresh_from_db()
        assert config_int.valor == "99"

    def test_ugp_can_read(self, api_client, config_int, super_admin_user, ugp_user, adt_user):
        api_client.force_authenticate(user=ugp_user)
        response = api_client.get("/api/v1/system-config/")
        assert response.status_code == status.HTTP_200_OK

        api_client.force_authenticate(user=adt_user)
        response = api_client.get("/api/v1/system-config/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_value_type_validation(
        self, api_client, config_int, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.patch(
            f"/api/v1/system-config/{config_int.chave}/", {"valor": "abc"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_chave_ignored(self, api_client, config_int, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.patch(
            f"/api/v1/system-config/{config_int.chave}/",
            {"chave": "nova_chave"},
        )
        assert response.status_code == status.HTTP_200_OK
        config_int.refresh_from_db()
        assert config_int.chave == "test_integer_param"

    def test_get_detail_returns_typed_value(
        self, api_client, config_int, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.get(
            f"/api/v1/system-config/{config_int.chave}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valor"] == 42
        assert isinstance(response.data["valor"], int)

    def test_get_list_returns_typed_value(
        self, api_client, config_int, super_admin_user
    ):
        SystemConfig.objects.create(
            chave="test_bool_param",
            valor="True",
            tipo=TipoConfiguracao.BOOLEAN,
        )
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.get("/api/v1/system-config/")
        assert response.status_code == status.HTTP_200_OK
        results = {r["chave"]: r for r in response.data["results"]}
        assert results["test_integer_param"]["valor"] == 42
        assert isinstance(results["test_integer_param"]["valor"], int)
        assert results["test_bool_param"]["valor"] is True
        assert isinstance(results["test_bool_param"]["valor"], bool)

    def test_patch_creates_audit_log_with_old_and_new_values(
        self, api_client, config_int, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.patch(
            f"/api/v1/system-config/{config_int.chave}/", {"valor": "99"}
        )
        assert response.status_code == status.HTTP_200_OK

        log = AuditLog.objects.filter(
            user=super_admin_user,
            acao="system_config_update",
        ).last()
        assert log is not None
        assert log.entidade_id == str(config_int.pk)
        assert log.valores_anteriores == {"valor": "42"}
        assert log.valores_novos == {"valor": "99"}
