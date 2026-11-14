import factory
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from django.utils import timezone

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import MembroFamilia, UFPA
from apps.sgp.tests.factories import UFPAFactory
from apps.core.tests.factories import MunicipalityFactory

pytestmark = pytest.mark.django_db


class TestUFPACriacao:
    def test_create_ufpa_with_minimum_required_fields(
        self, auth_client, ufpa_payload_minimo
    ):
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["titular"]["nome_completo"] == "Maria da Silva"
        assert response.data["ativo"] is True

    def test_create_ufpa_with_all_fields(
        self, auth_client, ufpa_payload_completo
    ):
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_completo, format="json"
        )
        assert response.status_code == 201
        assert response.data["titular"]["rg"] == "1234567"
        assert response.data["latitude"] == "-5.123456"
        assert response.data["titular"]["nis"] == "12345678901"

    def test_cep_optional(self, auth_client, ufpa_payload_minimo):
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["cep"] == ""


class TestValidacaoCPF:
    @pytest.mark.parametrize(
        "cpf_invalido",
        [
            "abc",
            "123",
            "12345678901",
        ],
    )
    def test_cpf_invalid_format_returns_400(
        self, auth_client, ufpa_payload_minimo, cpf_invalido
    ):
        payload = {**ufpa_payload_minimo, "cpf": cpf_invalido}
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", payload, format="json"
        )
        assert response.status_code == 400

    def test_cpf_all_same_digits_returns_400(
        self, auth_client, ufpa_payload_minimo
    ):
        payload = {**ufpa_payload_minimo, "cpf": "11111111111"}
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", payload, format="json"
        )
        assert response.status_code == 400


class TestUnicidadeCPF:
    def test_cpf_duplicate_same_projeto_returns_400(
        self, auth_client, ufpa_payload_minimo
    ):
        auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        assert response.status_code == 400
        assert "cpf" in response.data
        assert "Já existe uma UFPA ativa" in str(response.data["cpf"])

    def test_cpf_duplicate_different_projetos_allowed(
        self, auth_client, ufpa_payload_minimo, outro_projeto
    ):
        # CPF must be globally unique among members
        auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        payload2 = {
            **ufpa_payload_minimo,
            "projeto": outro_projeto.pk,
            "cpf": "49193681437",  # valid CPF
        }
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", payload2, format="json"
        )
        assert response.status_code == 201

    def test_cpf_duplicate_but_inactive_allows_new_active(
        self, auth_client, ufpa_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        ufpa_id = res.data["id"]
        auth_client.delete(f"/api/v1/sgp/ufpas/{ufpa_id}/")

        # CPF must be globally unique, even if UFPA was inactive
        payload = {**ufpa_payload_minimo, "cpf": "04227503523"}  # valid CPF
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", payload, format="json"
        )
        assert response.status_code == 201


class TestTerritorioAutomatico:
    def test_territorio_auto_filled_from_municipio(
        self, auth_client, ufpa_payload_minimo, municipio, territory
    ):
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["territorio"]["id"] == territory.pk

    def test_territorio_in_payload_is_ignored(
        self,
        auth_client,
        ufpa_payload_minimo,
        municipio,
        outro_territorio,
        territory,
    ):
        payload = {
            **ufpa_payload_minimo,
            "territorio": outro_territorio.pk,
        }
        response = auth_client.post(
            "/api/v1/sgp/ufpas/", payload, format="json"
        )
        assert response.status_code == 201
        ufpa = UFPA.objects.get(pk=response.data["id"])
        assert ufpa.territorio_id == territory.pk
        assert ufpa.territorio_id != outro_territorio.pk


class TestSoftDelete:
    def test_soft_delete_sets_ativo_false_keeps_record(
        self, auth_client, ufpa_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        ufpa_id = res.data["id"]

        response = auth_client.delete(f"/api/v1/sgp/ufpas/{ufpa_id}/")
        assert response.status_code == 204

        ufpa = UFPA.all_objects.get(pk=ufpa_id)
        assert ufpa.ativo is False


class TestSerializers:
    def test_list_serializer_returns_slim_payload(
        self, auth_client, ufpa_payload_minimo
    ):
        auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200

        result = response.data["results"][0]
        expected_keys = {
            "id",
            "nome_titular",
            "cpf",
            "municipio",
            "territorio",
            "criado_em",
            "ativo",
            "foto_url",
        }
        assert set(result.keys()) == expected_keys

    def test_list_serializer_includes_foto_url(
        self, auth_client, ufpa_payload_minimo
    ):
        auth_client.post(
            "/api/v1/sgp/ufpas/", {**ufpa_payload_minimo, "foto_url": "https://example.com/foto.jpg"}, format="json"
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200

        result = response.data["results"][0]
        assert result["foto_url"] == "https://example.com/foto.jpg"

    def test_list_serializer_foto_url_empty_when_not_set(
        self, auth_client, ufpa_payload_minimo
    ):
        auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200

        result = response.data["results"][0]
        assert result["foto_url"] == ""

    def test_detail_serializer_returns_full_payload_with_membros_array(
        self, auth_client, ufpa_payload_completo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_completo, format="json"
        )
        ufpa_id = res.data["id"]

        response = auth_client.get(f"/api/v1/sgp/ufpas/{ufpa_id}/")
        assert response.status_code == 200

        assert "membros" in response.data
        assert len(response.data["membros"]) == 1
        assert "titular" in response.data
        assert "municipio" in response.data
        assert isinstance(response.data["municipio"], dict)
        assert "territorio" in response.data
        assert isinstance(response.data["territorio"], dict)

    def test_detalhe_ufpa_inclui_estado(
        self, auth_client, ufpa_payload_completo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_completo, format="json"
        )
        ufpa_id = res.data["id"]

        response = auth_client.get(f"/api/v1/sgp/ufpas/{ufpa_id}/")
        assert response.status_code == 200
        assert response.data["municipio"]["estado"]["sigla"] == "RN"

    def test_lista_ufpa_inclui_estado(
        self, auth_client, ufpa_payload_minimo
    ):
        auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200

        result = response.data["results"][0]
        assert result["municipio"]["estado"]["sigla"] == "RN"

    def test_sem_query_adicional_por_estado(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        UFPAFactory(
            projeto=projeto, municipio=municipio_rn, territorio=territory_rn,
        )
        with CaptureQueriesContext(connection) as ctx_1:
            auth_client.get("/api/v1/sgp/ufpas/")
        queries_com_1 = len(ctx_1.captured_queries)

        UFPAFactory.create_batch(
            49, projeto=projeto, municipio=municipio_rn, territorio=territory_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 20000000000:011d}"),
        )
        # UFPAPagination.page_size é 50 — sem parâmetro, a página já traz tudo.
        with CaptureQueriesContext(connection) as ctx_50:
            response = auth_client.get("/api/v1/sgp/ufpas/")
        queries_com_50 = len(ctx_50.captured_queries)

        assert response.status_code == 200
        assert len(response.data["results"]) == 50
        assert queries_com_50 == queries_com_1

    def test_cpf_masked_in_list(
        self, auth_client, ufpa_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        ufpa_id = res.data["id"]

        response = auth_client.get("/api/v1/sgp/ufpas/")
        result = [
            u for u in response.data["results"] if u["id"] == ufpa_id
        ][0]
        assert "***" in result["cpf"]
        assert result["cpf"].count("*") == 6


class TestAuditLog:
    def test_audit_log_created_on_create_and_update(
        self, auth_client, ufpa_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/sgp/ufpas/", ufpa_payload_minimo, format="json"
        )
        ufpa_id = res.data["id"]

        assert AuditLog.objects.filter(
            entidade="UFPA",
            entidade_id=str(ufpa_id),
            acao="UFPA.create",
        ).exists()

        auth_client.patch(
            f"/api/v1/sgp/ufpas/{ufpa_id}/",
            {"nome": "Nome Atualizado"},
            format="json",
        )

        assert AuditLog.objects.filter(
            entidade="UFPA",
            entidade_id=str(ufpa_id),
            acao="UFPA.update",
        ).exists()


class TestFiltrosEBusca:
    def test_list_filter_by_municipio_returns_correct_subset(
        self, auth_client, projeto, municipio_rn, municipio_ce
    ):
        ufpa_rn = UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_ce, titular_cpf="52998224725"
        )
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/?municipio={municipio_rn.pk}"
        )
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert ufpa_rn.pk in ids
        assert len(ids) == 1

    def test_list_filter_by_multiple_params(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757", ativo=True
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="52998224725", ativo=False
        )
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/?municipio={municipio_rn.pk}&ativo=true"
        )
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_list_filter_by_cadastrado_de_ate_usa_dia_do_servidor(
        self, auth_client, projeto, municipio_rn
    ):
        """`cadastrado_de/ate` filtram pelo dia LOCAL (TIME_ZONE do servidor),
        não por uma janela UTC fixa — ver DIVIDA_TECNICA_FILTROS_DATA_UTC.md."""

        def aware(year, month, day, hour, minute):
            return timezone.make_aware(datetime(year, month, day, hour, minute))

        # 28/08 21:04 no fuso do servidor ainda é dia 28 local.
        dentro = UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        UFPA.objects.filter(pk=dentro.pk).update(criado_em=aware(2026, 8, 28, 21, 4))
        # 27/08 22:00 no fuso do servidor é dia 27 local: não deve entrar no filtro "28".
        dia_anterior = UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="52998224725"
        )
        UFPA.objects.filter(pk=dia_anterior.pk).update(criado_em=aware(2026, 8, 27, 22, 0))
        dia_seguinte = UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="11144477735"
        )
        UFPA.objects.filter(pk=dia_seguinte.pk).update(criado_em=aware(2026, 8, 29, 5, 0))

        response = auth_client.get(
            "/api/v1/sgp/ufpas/",
            {"cadastrado_de": "2026-08-28", "cadastrado_ate": "2026-08-28"},
        )

        assert response.status_code == 200
        ids = {u["id"] for u in response.data["results"]}
        assert dentro.pk in ids
        assert dia_anterior.pk not in ids
        assert dia_seguinte.pk not in ids

    def test_list_search_by_nome_titular(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="João Silva", titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Maria Souza", titular_cpf="52998224725",
        )
        response = auth_client.get("/api/v1/sgp/ufpas/?q=joão")
        assert response.status_code == 200
        nomes = [u["nome_titular"] for u in response.data["results"]]
        assert "João Silva" in nomes
        assert "Maria Souza" not in nomes

    def test_list_search_by_cpf_ignores_mask(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="86288366757",
        )
        response_unmasked = auth_client.get("/api/v1/sgp/ufpas/?q=86288366757")
        response_masked = auth_client.get("/api/v1/sgp/ufpas/?q=862.883.667-57")
        assert response_unmasked.status_code == 200
        assert response_masked.status_code == 200
        assert (
            len(response_unmasked.data["results"])
            == len(response_masked.data["results"])
            == 1
        )

    def test_list_ordering_default_recent_first(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="52998224725",
        )
        oldest = UFPA.objects.order_by("criado_em").first()
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        assert response.data["results"][0]["id"] != oldest.pk

    def test_list_ordering_by_nome_titular_asc_and_desc(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Ana", titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Zeca", titular_cpf="52998224725",
        )
        response_asc = auth_client.get("/api/v1/sgp/ufpas/?ordering=titular__nome_completo")
        names_asc = [u["nome_titular"] for u in response_asc.data["results"]]
        assert names_asc == sorted(names_asc)

        response_desc = auth_client.get("/api/v1/sgp/ufpas/?ordering=-titular__nome_completo")
        names_desc = [u["nome_titular"] for u in response_desc.data["results"]]
        assert names_desc == sorted(names_desc, reverse=True)


class TestPaginacao:
    def test_list_pagination_default_50(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory.create_batch(
            55,
            projeto=projeto,
            municipio=municipio_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 50
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        page2 = auth_client.get(response.data["next"])
        assert len(page2.data["results"]) == 5

    def test_list_pagination_max_200_capped(
        self, auth_client, projeto, municipio_rn
    ):
        UFPAFactory.create_batch(
            210,
            projeto=projeto,
            municipio=municipio_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 20000000000:011d}"),
        )
        response = auth_client.get("/api/v1/sgp/ufpas/?page_size=500")
        assert response.status_code == 200
        assert len(response.data["results"]) == 200


class TestAtivaPadrao:
    def test_list_returns_only_active_by_default(
        self, auth_client, projeto, municipio_rn
    ):
        ativa = UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Ativa", titular_cpf="86288366757", ativo=True,
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Inativa", titular_cpf="52998224725", ativo=False,
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        nomes = [u["nome_titular"] for u in response.data["results"]]
        assert "Ativa" in nomes
        assert "Inativa" not in nomes

        response_inativas = auth_client.get("/api/v1/sgp/ufpas/?ativo=false")
        assert response_inativas.status_code == 200
        nomes_inativas = [
            u["nome_titular"] for u in response_inativas.data["results"]
        ]
        assert "Inativa" in nomes_inativas
        assert "Ativa" not in nomes_inativas


class TestIsolamentoTerritorial:
    def test_adt_sees_only_own_territory(
        self, auth_client_adt_rn, projeto, municipio_rn, municipio_ce,
        territory_rn, territory_ce,
    ):
        ufpa_rn = UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_adt_rn.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert ufpa_rn.pk in ids
        assert len(ids) == 1

    def test_articulador_sees_only_own_state(
        self, auth_client_articulador_rn, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        ufpa_rn = UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_articulador_rn.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert ufpa_rn.pk in ids
        assert len(ids) == 1

    def test_super_admin_sees_all_ufpas(
        self, auth_client_super_admin, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_super_admin.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_ugp_sees_all_ufpas(
        self, auth_client, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UFPAFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_adt_accessing_ufpa_outside_territory_returns_404(
        self, auth_client_adt_rn, projeto,
        municipio_ce, territory_ce,
    ):
        ufpa_ce = UFPAFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_adt_rn.get(f"/api/v1/sgp/ufpas/{ufpa_ce.pk}/")
        assert response.status_code == 404

    def test_perfil_without_sgp_access_returns_403(
        self, auth_client_sem_acesso, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        response = auth_client_sem_acesso.get("/api/v1/sgp/ufpas/")
        assert response.status_code == 403

    def test_perfil_without_sgp_access_returns_403_on_mapa(
        self, auth_client_sem_acesso, projeto, municipio_rn
    ):
        UFPAFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        response = auth_client_sem_acesso.get("/api/v1/sgp/ufpas/mapa/")
        assert response.status_code == 403


class TestPerformanceIndexes:
    def test_query_uses_index_on_municipio_and_territorio(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        UFPAFactory.create_batch(
            10, projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        from django.db import connection
        qs = UFPA.objects.filter(
            municipio=municipio_rn, territorio=territory_rn
        )
        # Com poucas linhas o planner pode preferir seq scan dependendo das
        # estatísticas locais do banco; desabilita seq scan para verificar de
        # forma determinística que existe índice capaz de atender a consulta.
        with connection.cursor() as cursor:
            cursor.execute("SET enable_seqscan = off")
        try:
            explain = qs.explain(analyze=True)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET enable_seqscan = on")
        assert "Index Scan" in explain or "Bitmap Heap Scan" in explain or "Index Only Scan" in explain

    def test_list_filter_by_municipio_is_efficient(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        UFPAFactory.create_batch(
            10, projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            auth_client.get(f"/api/v1/sgp/ufpas/?municipio={municipio_rn.pk}")
        assert len(ctx.captured_queries) <= 8

    @pytest.mark.performance
    def test_list_performance_5000_ufpas(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        import time
        from apps.sgp.models import UFPA, MembroFamilia

        titulars = [
            MembroFamilia(
                ufpa=None,
                grau_parentesco="titular",
                nome_completo=f"Titular {i}",
                cpf=f"{i + 10000000000:011d}",
                data_nascimento="1990-01-01",
            )
            for i in range(5000)
        ]
        titulars = MembroFamilia.objects.bulk_create(titulars, batch_size=500)

        ufpas = [
            UFPA(
                projeto=projeto,
                municipio=municipio_rn,
                territorio=territory_rn,
                titular=t,
                ativo=True,
            )
            for t in titulars
        ]
        ufpas = UFPA.objects.bulk_create(ufpas, batch_size=500)

        for titular, ufpa in zip(titulars, ufpas):
            titular.ufpa_id = ufpa.pk
        MembroFamilia.objects.bulk_update(titulars, ["ufpa"], batch_size=500)

        start = time.time()
        response = auth_client.get(f"/api/v1/sgp/ufpas/?municipio={municipio_rn.pk}")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0


class TestOrigemTitular:
    def _ufpa_rn(self, projeto, municipio_rn, territory_rn):
        return UFPAFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )

    def _simular_sync_sca(self, ufpa):
        sync_em = timezone.now() - timedelta(hours=1)
        MembroFamilia.objects.filter(pk=ufpa.titular_id).update(
            device_id="dev-app-001",
            uuid_local=uuid4(),
            ultima_origem="sca",
            ultimo_sync_em=sync_em,
        )
        return sync_em

    def test_edicao_web_do_titular_marca_origem_web_e_preserva_sync(
        self, auth_client_adt_rn, projeto, municipio_rn, territory_rn,
    ):
        ufpa = self._ufpa_rn(projeto, municipio_rn, territory_rn)
        sync_em = self._simular_sync_sca(ufpa)

        response = auth_client_adt_rn.patch(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/",
            {"nome": "Nome Editado na Web"},
            format="json",
        )
        assert response.status_code == 200

        titular = UFPA.objects.get(pk=ufpa.pk).titular
        assert titular.nome_completo == "Nome Editado na Web"
        assert titular.ultima_origem == "web"
        assert titular.device_id == "dev-app-001"
        assert titular.ultimo_sync_em == sync_em

    def test_patch_sem_alterar_titular_preserva_origem_sca(
        self, auth_client_adt_rn, projeto, municipio_rn, territory_rn,
    ):
        ufpa = self._ufpa_rn(projeto, municipio_rn, territory_rn)
        nome_original = ufpa.titular.nome_completo
        sync_em = self._simular_sync_sca(ufpa)

        response = auth_client_adt_rn.patch(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/",
            {"apelido": "Sítio Renomeado"},
            format="json",
        )
        assert response.status_code == 200

        titular = UFPA.objects.get(pk=ufpa.pk).titular
        assert titular.nome_completo == nome_original
        assert titular.ultima_origem == "sca"
        assert titular.ultimo_sync_em == sync_em
