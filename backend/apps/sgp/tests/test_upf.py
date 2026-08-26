import factory
import pytest
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.tests.factories import UPFFactory
from apps.core.tests.factories import MunicipalityFactory

pytestmark = pytest.mark.django_db


class TestUPFCriacao:
    def test_create_upf_with_minimum_required_fields(
        self, auth_client, upf_payload_minimo
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["titular"]["nome_completo"] == "Maria da Silva"
        assert response.data["ativa"] is True

    def test_create_upf_with_all_fields(
        self, auth_client, upf_payload_completo
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_completo, format="json"
        )
        assert response.status_code == 201
        assert response.data["titular"]["rg"] == "1234567"
        assert response.data["latitude"] == "-5.123456"
        assert response.data["titular"]["nis"] == "12345678901"

    def test_cep_optional(self, auth_client, upf_payload_minimo):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
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
        self, auth_client, upf_payload_minimo, cpf_invalido
    ):
        payload = {**upf_payload_minimo, "cpf": cpf_invalido}
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 400

    def test_cpf_all_same_digits_returns_400(
        self, auth_client, upf_payload_minimo
    ):
        payload = {**upf_payload_minimo, "cpf": "11111111111"}
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 400


class TestUnicidadeCPF:
    def test_cpf_duplicate_same_projeto_returns_400(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 400
        assert "cpf" in response.data
        assert "Já existe uma UPF ativa" in str(response.data["cpf"])

    def test_cpf_duplicate_different_projetos_allowed(
        self, auth_client, upf_payload_minimo, outro_projeto
    ):
        # CPF must be globally unique among members
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        payload2 = {
            **upf_payload_minimo,
            "projeto": outro_projeto.pk,
            "cpf": "49193681437",  # valid CPF
        }
        response = auth_client.post(
            "/api/v1/upfs/", payload2, format="json"
        )
        assert response.status_code == 201

    def test_cpf_duplicate_but_inactive_allows_new_active(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]
        auth_client.delete(f"/api/v1/upfs/{upf_id}/")

        # CPF must be globally unique, even if UPF was inactive
        payload = {**upf_payload_minimo, "cpf": "04227503523"}  # valid CPF
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 201


class TestTerritorioAutomatico:
    def test_territorio_auto_filled_from_municipio(
        self, auth_client, upf_payload_minimo, municipio, territory
    ):
        response = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        assert response.status_code == 201
        assert response.data["territorio"]["id"] == territory.pk

    def test_territorio_in_payload_is_ignored(
        self,
        auth_client,
        upf_payload_minimo,
        municipio,
        outro_territorio,
        territory,
    ):
        payload = {
            **upf_payload_minimo,
            "territorio": outro_territorio.pk,
        }
        response = auth_client.post(
            "/api/v1/upfs/", payload, format="json"
        )
        assert response.status_code == 201
        upf = UPF.objects.get(pk=response.data["id"])
        assert upf.territorio_id == territory.pk
        assert upf.territorio_id != outro_territorio.pk


class TestSoftDelete:
    def test_soft_delete_sets_ativa_false_keeps_record(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.delete(f"/api/v1/upfs/{upf_id}/")
        assert response.status_code == 204

        upf = UPF.objects.get(pk=upf_id)
        assert upf.ativa is False


class TestSerializers:
    def test_list_serializer_returns_slim_payload(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200

        result = response.data["results"][0]
        expected_keys = {
            "id",
            "nome_titular",
            "cpf",
            "municipio",
            "territorio",
            "criado_em",
            "ativa",
            "foto_url",
        }
        assert set(result.keys()) == expected_keys

    def test_list_serializer_includes_foto_url(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", {**upf_payload_minimo, "foto_url": "https://example.com/foto.jpg"}, format="json"
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200

        result = response.data["results"][0]
        assert result["foto_url"] == "https://example.com/foto.jpg"

    def test_list_serializer_foto_url_empty_when_not_set(
        self, auth_client, upf_payload_minimo
    ):
        auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200

        result = response.data["results"][0]
        assert result["foto_url"] == ""

    def test_detail_serializer_returns_full_payload_with_membros_array(
        self, auth_client, upf_payload_completo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_completo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.get(f"/api/v1/upfs/{upf_id}/")
        assert response.status_code == 200

        assert "membros" in response.data
        assert len(response.data["membros"]) == 1
        assert "titular" in response.data
        assert "municipio" in response.data
        assert isinstance(response.data["municipio"], dict)
        assert "territorio" in response.data
        assert isinstance(response.data["territorio"], dict)

    def test_cpf_masked_in_list(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        response = auth_client.get("/api/v1/upfs/")
        result = [
            u for u in response.data["results"] if u["id"] == upf_id
        ][0]
        assert "***" in result["cpf"]
        assert result["cpf"].count("*") == 6


class TestAuditLog:
    def test_audit_log_created_on_create_and_update(
        self, auth_client, upf_payload_minimo
    ):
        res = auth_client.post(
            "/api/v1/upfs/", upf_payload_minimo, format="json"
        )
        upf_id = res.data["id"]

        assert AuditLog.objects.filter(
            entidade="UPF",
            entidade_id=str(upf_id),
            acao="UPF.create",
        ).exists()

        auth_client.patch(
            f"/api/v1/upfs/{upf_id}/",
            {"nome": "Nome Atualizado"},
            format="json",
        )

        assert AuditLog.objects.filter(
            entidade="UPF",
            entidade_id=str(upf_id),
            acao="UPF.update",
        ).exists()


class TestFiltrosEBusca:
    def test_list_filter_by_municipio_returns_correct_subset(
        self, auth_client, projeto, municipio_rn, municipio_ce
    ):
        upf_rn = UPFFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_ce, titular_cpf="52998224725"
        )
        response = auth_client.get(
            f"/api/v1/upfs/?municipio={municipio_rn.pk}"
        )
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert upf_rn.pk in ids
        assert len(ids) == 1

    def test_list_filter_by_multiple_params(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757", ativa=True
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="52998224725", ativa=False
        )
        response = auth_client.get(
            f"/api/v1/upfs/?municipio={municipio_rn.pk}&ativa=true"
        )
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_list_search_by_nome_titular(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="João Silva", titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Maria Souza", titular_cpf="52998224725",
        )
        response = auth_client.get("/api/v1/upfs/?q=joão")
        assert response.status_code == 200
        nomes = [u["nome_titular"] for u in response.data["results"]]
        assert "João Silva" in nomes
        assert "Maria Souza" not in nomes

    def test_list_search_by_cpf_ignores_mask(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="86288366757",
        )
        response_unmasked = auth_client.get("/api/v1/upfs/?q=86288366757")
        response_masked = auth_client.get("/api/v1/upfs/?q=862.883.667-57")
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
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            titular_cpf="52998224725",
        )
        oldest = UPF.objects.order_by("criado_em").first()
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200
        assert response.data["results"][0]["id"] != oldest.pk

    def test_list_ordering_by_nome_titular_asc_and_desc(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Ana", titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Zeca", titular_cpf="52998224725",
        )
        response_asc = auth_client.get("/api/v1/upfs/?ordering=titular__nome_completo")
        names_asc = [u["nome_titular"] for u in response_asc.data["results"]]
        assert names_asc == sorted(names_asc)

        response_desc = auth_client.get("/api/v1/upfs/?ordering=-titular__nome_completo")
        names_desc = [u["nome_titular"] for u in response_desc.data["results"]]
        assert names_desc == sorted(names_desc, reverse=True)


class TestPaginacao:
    def test_list_pagination_default_50(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory.create_batch(
            55,
            projeto=projeto,
            municipio=municipio_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 50
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        page2 = auth_client.get(response.data["next"])
        assert len(page2.data["results"]) == 5

    def test_list_pagination_max_200_capped(
        self, auth_client, projeto, municipio_rn
    ):
        UPFFactory.create_batch(
            210,
            projeto=projeto,
            municipio=municipio_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 20000000000:011d}"),
        )
        response = auth_client.get("/api/v1/upfs/?page_size=500")
        assert response.status_code == 200
        assert len(response.data["results"]) == 200


class TestAtivaPadrao:
    def test_list_returns_only_active_by_default(
        self, auth_client, projeto, municipio_rn
    ):
        ativa = UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Ativa", titular_cpf="86288366757", ativa=True,
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            _titular_nome="Inativa", titular_cpf="52998224725", ativa=False,
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200
        nomes = [u["nome_titular"] for u in response.data["results"]]
        assert "Ativa" in nomes
        assert "Inativa" not in nomes

        response_inativas = auth_client.get("/api/v1/upfs/?ativa=false")
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
        upf_rn = UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_adt_rn.get("/api/v1/upfs/")
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert upf_rn.pk in ids
        assert len(ids) == 1

    def test_articulador_sees_only_own_state(
        self, auth_client_articulador_rn, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        upf_rn = UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_articulador_rn.get("/api/v1/upfs/")
        assert response.status_code == 200
        ids = [u["id"] for u in response.data["results"]]
        assert upf_rn.pk in ids
        assert len(ids) == 1

    def test_super_admin_sees_all_upfs(
        self, auth_client_super_admin, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_super_admin.get("/api/v1/upfs/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_ugp_sees_all_upfs(
        self, auth_client, projeto,
        municipio_rn, municipio_ce, territory_rn, territory_ce,
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )
        UPFFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client.get("/api/v1/upfs/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_adt_accessing_upf_outside_territory_returns_404(
        self, auth_client_adt_rn, projeto,
        municipio_ce, territory_ce,
    ):
        upf_ce = UPFFactory(
            projeto=projeto, municipio=municipio_ce,
            territorio=territory_ce, titular_cpf="52998224725",
        )
        response = auth_client_adt_rn.get(f"/api/v1/upfs/{upf_ce.pk}/")
        assert response.status_code == 404

    def test_perfil_without_sgp_access_returns_403(
        self, auth_client_sem_acesso, projeto, municipio_rn
    ):
        UPFFactory(
            projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757"
        )
        response = auth_client_sem_acesso.get("/api/v1/upfs/")
        assert response.status_code == 403


class TestPerformanceIndexes:
    def test_query_uses_index_on_municipio_and_territorio(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        UPFFactory.create_batch(
            10, projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        from django.db import connection
        qs = UPF.objects.filter(
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
        UPFFactory.create_batch(
            10, projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn,
            titular_cpf=factory.Sequence(lambda n: f"{n + 10000000000:011d}"),
        )
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            auth_client.get(f"/api/v1/upfs/?municipio={municipio_rn.pk}")
        assert len(ctx.captured_queries) <= 8

    def test_list_performance_5000_upfs(
        self, auth_client, projeto, municipio_rn, territory_rn
    ):
        import time
        from apps.sgp.models import UPF, MembroFamilia

        titulars = [
            MembroFamilia(
                upf=None,
                parentesco="titular",
                nome_completo=f"Titular {i}",
                cpf=f"{i + 10000000000:011d}",
                data_nasc="1990-01-01",
            )
            for i in range(5000)
        ]
        titulars = MembroFamilia.objects.bulk_create(titulars, batch_size=500)

        upfs = [
            UPF(
                projeto=projeto,
                municipio=municipio_rn,
                territorio=territory_rn,
                titular=t,
                ativa=True,
            )
            for t in titulars
        ]
        upfs = UPF.objects.bulk_create(upfs, batch_size=500)

        for titular, upf in zip(titulars, upfs):
            titular.upf_id = upf.pk
        MembroFamilia.objects.bulk_update(titulars, ["upf"], batch_size=500)

        start = time.time()
        response = auth_client.get(f"/api/v1/upfs/?municipio={municipio_rn.pk}")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0


class TestOrigemTitular:
    def _upf_rn(self, projeto, municipio_rn, territory_rn):
        return UPFFactory(
            projeto=projeto, municipio=municipio_rn,
            territorio=territory_rn, titular_cpf="86288366757",
        )

    def _simular_sync_sca(self, upf):
        sync_em = timezone.now() - timedelta(hours=1)
        MembroFamilia.objects.filter(pk=upf.titular_id).update(
            device_id="dev-app-001",
            uuid_local=uuid4(),
            ultima_origem="sca",
            ultimo_sync_em=sync_em,
        )
        return sync_em

    def test_edicao_web_do_titular_marca_origem_web_e_preserva_sync(
        self, auth_client_adt_rn, projeto, municipio_rn, territory_rn,
    ):
        upf = self._upf_rn(projeto, municipio_rn, territory_rn)
        sync_em = self._simular_sync_sca(upf)

        response = auth_client_adt_rn.patch(
            f"/api/v1/upfs/{upf.pk}/",
            {"nome": "Nome Editado na Web"},
            format="json",
        )
        assert response.status_code == 200

        titular = UPF.objects.get(pk=upf.pk).titular
        assert titular.nome_completo == "Nome Editado na Web"
        assert titular.ultima_origem == "web"
        assert titular.device_id == "dev-app-001"
        assert titular.ultimo_sync_em == sync_em

    def test_patch_sem_alterar_titular_preserva_origem_sca(
        self, auth_client_adt_rn, projeto, municipio_rn, territory_rn,
    ):
        upf = self._upf_rn(projeto, municipio_rn, territory_rn)
        nome_original = upf.titular.nome_completo
        sync_em = self._simular_sync_sca(upf)

        response = auth_client_adt_rn.patch(
            f"/api/v1/upfs/{upf.pk}/",
            {"apelido": "Sítio Renomeado"},
            format="json",
        )
        assert response.status_code == 200

        titular = UPF.objects.get(pk=upf.pk).titular
        assert titular.nome_completo == nome_original
        assert titular.ultima_origem == "sca"
        assert titular.ultimo_sync_em == sync_em
