from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from apps.core.models.audit_log import AuditLog
from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.utils import get_config
from apps.sgp.models import GoogleCalendarSyncEvent
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

SEED_KEYS = [
    "budget_subexec_alert_months",
    "budget_subexec_min_pct",
    "budget_transfer_alert_pct",
    "session_timeout_hours",
    "max_login_attempts",
    "lockout_minutes",
    "notification_demand_alert_days",
    "notification_form_deadline_days",
    "user_inactive_alert_days",
    "backup_retention_days",
    "sca_sync_batch_limit",
    "report_export_row_limit",
    "google_calendar_calendario_destino_id",
    "google_calendar_lembretes",
    "google_calendar_integracao_ativa",
]


class TestSeeds:
    """Tests for data migration seeds (0012_seed_system_config)."""

    def test_seeds_create_all_default_parameters(self):
        assert SystemConfig.objects.count() >= len(SEED_KEYS)
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

    def test_get_list_returns_typed_value(self, api_client, super_admin_user):
        SystemConfig.objects.create(
            chave="aaa_test_integer_param",
            valor="42",
            tipo=TipoConfiguracao.INTEGER,
        )
        SystemConfig.objects.create(
            chave="aaa_test_bool_param",
            valor="True",
            tipo=TipoConfiguracao.BOOLEAN,
        )
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.get("/api/v1/system-config/")
        assert response.status_code == status.HTTP_200_OK
        results = {r["chave"]: r for r in response.data["results"]}
        assert results["aaa_test_integer_param"]["valor"] == 42
        assert isinstance(results["aaa_test_integer_param"]["valor"], int)
        assert results["aaa_test_bool_param"]["valor"] is True
        assert isinstance(results["aaa_test_bool_param"]["valor"], bool)

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
            acao="system_config.updated",
        ).last()
        assert log is not None
        assert log.entidade_id == str(config_int.pk)
        assert log.valores_anteriores == {"valor": "42"}
        assert log.valores_novos == {"valor": "99"}


class TestGoogleCalendarConfigAPI:
    url = "/api/v1/core/config/google-calendar/"

    def test_get_returns_default_config(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "calendario_destino_id": "",
            "lembretes": [1440, 60],
            "integracao_ativa": False,
        }

    def test_non_super_admin_receives_403(self, api_client, ugp_user):
        api_client.force_authenticate(user=ugp_user)

        get_response = api_client.get(self.url)
        patch_response = api_client.patch(
            self.url,
            {"integracao_ativa": True},
        )

        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        assert patch_response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_integracao_ativa_false_then_true_persists(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)

        false_response = api_client.patch(self.url, {"integracao_ativa": False})
        assert false_response.status_code == status.HTTP_200_OK
        assert false_response.data["integracao_ativa"] is False

        true_response = api_client.patch(self.url, {"integracao_ativa": True})
        assert true_response.status_code == status.HTTP_200_OK
        assert true_response.data["integracao_ativa"] is True

        config = SystemConfig.objects.get(
            chave="google_calendar_integracao_ativa"
        )
        assert config.valor == "True"
        assert config.atualizado_por == super_admin_user

    def test_patch_calendario_destino_generates_audit_log(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        config = SystemConfig.objects.get(
            chave="google_calendar_calendario_destino_id"
        )

        response = api_client.patch(
            self.url,
            {"calendario_destino_id": "primary@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["calendario_destino_id"] == "primary@example.com"

        log = AuditLog.objects.filter(
            user=super_admin_user,
            acao="system_config.updated",
            entidade="SystemConfig",
            entidade_id=str(config.pk),
        ).last()
        assert log is not None
        assert log.valores_anteriores == {"valor": ""}
        assert log.valores_novos == {"valor": "primary@example.com"}

    def test_patch_validates_lembretes(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)

        response = api_client.patch(self.url, {"lembretes": [1440, 60]})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["lembretes"] == [1440, 60]

        invalid_response = api_client.patch(self.url, {"lembretes": [0]})
        assert invalid_response.status_code == status.HTTP_400_BAD_REQUEST


class TestGoogleCalendarStatusAPI:
    url = "/api/v1/core/config/google-calendar/status/"

    def test_unauthenticated_receives_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_super_admin_receives_403(self, api_client, ugp_user):
        api_client.force_authenticate(user=ugp_user)
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nunca_executada_quando_nenhum_evento_existe(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "estado": "nunca_executada",
            "ultima_sincronizacao": None,
            "ultimo_erro": None,
            "falhas_recentes": 0,
        }

    def test_estado_ok_apos_sucesso(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        GoogleCalendarSyncEvent.objects.create(activity=activity, sucesso=True)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["estado"] == "ok"
        assert response.data["ultima_sincronizacao"] is not None
        assert response.data["ultima_sincronizacao"].endswith("-03:00")
        assert response.data["ultimo_erro"] is None
        assert response.data["falhas_recentes"] == 0

    def test_estado_erro_mantem_ultima_sincronizacao_do_sucesso_anterior(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        sucesso = GoogleCalendarSyncEvent.objects.create(activity=activity, sucesso=True)
        GoogleCalendarSyncEvent.objects.filter(pk=sucesso.pk).update(
            ocorrido_em=timezone.now() - timedelta(hours=2)
        )
        GoogleCalendarSyncEvent.objects.create(
            activity=activity, sucesso=False, mensagem_erro="Google indisponível"
        )

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["estado"] == "erro"
        assert response.data["ultimo_erro"] == "Google indisponível"
        assert response.data["ultima_sincronizacao"] is not None

    def test_falhas_dentro_de_24h_sao_somadas(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        for _ in range(3):
            GoogleCalendarSyncEvent.objects.create(
                activity=activity, sucesso=False, mensagem_erro="erro"
            )

        response = api_client.get(self.url)

        assert response.data["falhas_recentes"] == 3

    def test_falha_fora_de_24h_nao_e_contada(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        antiga = GoogleCalendarSyncEvent.objects.create(
            activity=activity, sucesso=False, mensagem_erro="erro antigo"
        )
        GoogleCalendarSyncEvent.objects.filter(pk=antiga.pk).update(
            ocorrido_em=timezone.now() - timedelta(hours=25)
        )

        response = api_client.get(self.url)

        assert response.data["falhas_recentes"] == 0
        assert response.data["estado"] == "erro"

    def test_falhas_recentes_nao_zera_apos_sucesso(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        GoogleCalendarSyncEvent.objects.create(
            activity=activity, sucesso=False, mensagem_erro="erro 1"
        )
        GoogleCalendarSyncEvent.objects.create(
            activity=activity, sucesso=False, mensagem_erro="erro 2"
        )
        GoogleCalendarSyncEvent.objects.create(activity=activity, sucesso=True)

        response = api_client.get(self.url)

        assert response.data["estado"] == "ok"
        assert response.data["falhas_recentes"] == 2

    def test_pendente_tem_prioridade_sobre_eventos_passados(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        GoogleCalendarSyncEvent.objects.create(
            activity=ActivityFactory(), sucesso=True
        )
        GoogleCalendarSyncEvent.objects.create(
            activity=ActivityFactory(), sucesso=False, mensagem_erro="erro"
        )
        ActivityFactory(google_calendar_sync_status="pendente")

        response = api_client.get(self.url)

        assert response.data["estado"] == "pendente"

    def test_editar_activity_sem_sync_nao_altera_status(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)
        activity = ActivityFactory()
        GoogleCalendarSyncEvent.objects.create(activity=activity, sucesso=True)

        antes = api_client.get(self.url).data

        activity.descricao_narrativa = "Texto alterado diretamente no teste."
        activity.save(update_fields=["descricao_narrativa"])

        depois = api_client.get(self.url).data

        assert antes == depois
        assert GoogleCalendarSyncEvent.objects.count() == 1

    def test_resposta_bate_com_contrato_do_frontend(
        self, api_client, super_admin_user
    ):
        api_client.force_authenticate(user=super_admin_user)

        response = api_client.get(self.url)

        assert set(response.data.keys()) == {
            "estado",
            "ultima_sincronizacao",
            "ultimo_erro",
            "falhas_recentes",
        }
        assert response.data["estado"] in {"ok", "pendente", "erro", "nunca_executada"}
        assert isinstance(response.data["falhas_recentes"], int)


class TestParametrosDoOrcamento:
    @pytest.fixture
    def cliente(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        return api_client

    def _patch(self, cliente, chave, valor):
        return cliente.patch(f"/api/v1/system-config/{chave}/", {"valor": valor}, format="json")

    @pytest.mark.parametrize("chave, valor, aceito", [
        ("budget_limit_period", "anual", False),
        ("budget_limit_period", "semestral", True),
        ("budget_limit_period", "vigencia", True),
        ("budget_subexec_alert_months", 0, False),
        ("budget_subexec_alert_months", 25, False),
        ("budget_subexec_alert_months", 24, True),
        ("budget_subexec_min_pct", 0, False),
        ("budget_subexec_min_pct", 101, False),
        ("budget_subexec_min_pct", 100, True),
        ("budget_transfer_alert_pct", -5, False),
        ("budget_transfer_alert_pct", 1, True),
        ("budget_alert_yellow_pct", 0, False),
        ("budget_alert_red_pct", 101, False),
    ])
    def test_opcoes_e_faixas(self, cliente, chave, valor, aceito):
        antes = SystemConfig.objects.get(chave=chave).valor

        resposta = self._patch(cliente, chave, valor)

        if aceito:
            assert resposta.status_code == status.HTTP_200_OK, resposta.data
            assert SystemConfig.objects.get(chave=chave).valor == str(valor)
        else:
            assert resposta.status_code == status.HTTP_400_BAD_REQUEST
            assert "valor" in resposta.data
            assert SystemConfig.objects.get(chave=chave).valor == antes

    @pytest.mark.parametrize("chave, valor, aceito", [
        ("budget_alert_yellow_pct", 90, False),
        ("budget_alert_yellow_pct", 89, True),
        ("budget_alert_red_pct", 70, False),
        ("budget_alert_red_pct", 71, True),
    ])
    def test_amarelo_precisa_ser_menor_que_o_vermelho(self, cliente, chave, valor, aceito):
        SystemConfig.objects.filter(chave="budget_alert_yellow_pct").update(valor="70")
        SystemConfig.objects.filter(chave="budget_alert_red_pct").update(valor="90")

        resposta = self._patch(cliente, chave, valor)

        assert resposta.status_code == (status.HTTP_200_OK if aceito else status.HTTP_400_BAD_REQUEST)

    def test_a_conferencia_usa_o_valor_gravado_depois_de_uma_alteracao(self, cliente):
        assert self._patch(cliente, "budget_alert_yellow_pct", 80).status_code == status.HTTP_200_OK

        resposta = self._patch(cliente, "budget_alert_red_pct", 80)

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert "amarelo (80%)" in str(resposta.data["valor"])

    def test_parametro_fora_do_orcamento_so_confere_o_tipo(self, cliente):
        assert self._patch(cliente, "session_timeout_hours", 0).status_code == status.HTTP_200_OK


class TestParametrosDoOrcamentoNoAdmin:
    """O Django Admin aplica as mesmas regras do PATCH."""

    def _formulario(self, chave, valor):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        from apps.core.tests.factories import UserFactory

        config = SystemConfig.objects.get(chave=chave)
        request = RequestFactory().post("/")
        request.user = UserFactory(is_superuser=True)
        Formulario = site._registry[SystemConfig].get_form(request, config)
        return Formulario(data={"valor": valor, "descricao": config.descricao}, instance=config)

    @pytest.mark.parametrize("chave, valor, aceito", [
        ("budget_limit_period", "anual", False),
        ("budget_limit_period", "mensal", True),
        ("budget_subexec_min_pct", "0", False),
        ("budget_subexec_alert_months", "abc", False),
        ("budget_alert_yellow_pct", "95", False),
        ("budget_alert_yellow_pct", "80", True),
    ])
    def test_opcoes_faixas_e_limiares(self, chave, valor, aceito):
        SystemConfig.objects.filter(chave="budget_alert_yellow_pct").update(valor="70")
        SystemConfig.objects.filter(chave="budget_alert_red_pct").update(valor="90")

        formulario = self._formulario(chave, valor)
        formulario.is_valid()

        assert ("valor" not in formulario.errors) is aceito, formulario.errors
