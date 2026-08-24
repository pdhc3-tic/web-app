from datetime import date, timedelta

import pytest
from decimal import Decimal

from apps.sgp.models import WorkPlanMeta, WorkPlanAcao
from apps.sgp.tests.factories import ActivityFactory, WorkPlanAcaoFactory, WorkPlanMetaFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def meta(db, usuario):
    return WorkPlanMetaFactory(
        numero=1,
        titulo="Meta Teste",
        data_inicio=date(2025, 11, 1),
        data_fim=date(2027, 10, 31),
        criado_por=usuario,
    )


@pytest.fixture
def meta_payload(usuario):
    return {
        "numero": 2,
        "titulo": "Meta Criada via API",
        "descricao": "Descrição da meta",
        "ods_ids": [1, 2],
        "data_inicio": "2025-11-01",
        "data_fim": "2027-10-31",
    }


@pytest.fixture
def acao_payload(meta):
    return {
        "meta": meta.pk,
        "numero": "1.1",
        "descricao": "Ação de teste",
        "tipo_unidade": 11,
        "quantidade_planejada": "100.00",
        "valor_unitario": "500.00",
        "data_inicio": "2025-11-01",
        "data_fim": "2027-10-31",
    }


@pytest.fixture
def acao(meta):
    return WorkPlanAcaoFactory(
        meta=meta,
        numero="1.1",
        quantidade_planejada=Decimal("100.00"),
        valor_unitario=Decimal("500.00"),
    )


# ===================================================================
#  ISSUE #134 — META
# ===================================================================

class TestWorkPlanMetaCriacao:
    def test_create_meta_with_minimum_fields(self, auth_client, meta_payload):
        response = auth_client.post("/api/v1/metas/", meta_payload, format="json")
        assert response.status_code == 201
        assert response.data["numero"] == 2
        assert response.data["titulo"] == "Meta Criada via API"
        assert response.data["status_calculado"] == "no_prazo"

    def test_create_meta_with_all_fields(self, auth_client, meta_payload):
        response = auth_client.post("/api/v1/metas/", meta_payload, format="json")
        assert response.status_code == 201
        assert response.data["ods_ids"] == [1, 2]
        assert response.data["descricao"] == "Descrição da meta"

    def test_criado_por_auto_filled(self, auth_client, meta_payload):
        response = auth_client.post("/api/v1/metas/", meta_payload, format="json")
        assert response.status_code == 201
        assert response.data["criado_por"] is not None


class TestMetaUnicidadeNumero:
    def test_duplicate_numero_returns_400(self, auth_client, meta_payload):
        auth_client.post("/api/v1/metas/", meta_payload, format="json")
        response = auth_client.post("/api/v1/metas/", meta_payload, format="json")
        assert response.status_code == 400
        assert "numero" in response.data

    def test_numero_out_of_range_returns_400(self, auth_client, meta_payload):
        response = auth_client.post(
            "/api/v1/metas/", {**meta_payload, "numero": 8}, format="json"
        )
        assert response.status_code == 400

    def test_numero_zero_returns_400(self, auth_client, meta_payload):
        response = auth_client.post(
            "/api/v1/metas/", {**meta_payload, "numero": 0}, format="json"
        )
        assert response.status_code == 400


class TestMetaPermissoes:
    def test_ugp_can_create(self, auth_client, meta_payload):
        assert auth_client.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 201

    def test_super_admin_can_create(self, auth_client_super_admin, meta_payload):
        assert auth_client_super_admin.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 201

    def test_adt_cannot_create(self, auth_client_adt_rn, meta_payload):
        assert auth_client_adt_rn.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 403

    def test_articulador_cannot_create(self, auth_client_articulador_rn, meta_payload):
        assert auth_client_articulador_rn.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 403

    def test_agricultor_cannot_create(self, auth_client_sem_acesso, meta_payload):
        assert auth_client_sem_acesso.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 403

    def test_unauthenticated_returns_401(self, api_client, meta_payload):
        assert api_client.post(
            "/api/v1/metas/", meta_payload, format="json"
        ).status_code == 401

    def test_any_authenticated_can_list(self, auth_client_adt_rn, meta):
        assert auth_client_adt_rn.get("/api/v1/metas/").status_code == 200

    def test_adt_lists_only_metas_with_actions_in_own_territory(
        self, auth_client_adt_rn, municipio_rn, municipio_ce
    ):
        visible_meta = WorkPlanMetaFactory(numero=1)
        hidden_meta = WorkPlanMetaFactory(numero=2)
        visible_action = WorkPlanAcaoFactory(meta=visible_meta, numero="1.1")
        hidden_action = WorkPlanAcaoFactory(meta=hidden_meta, numero="2.1")
        ActivityFactory(acao=visible_action, municipio=municipio_rn, status="concluido")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_adt_rn.get("/api/v1/metas/")

        assert response.status_code == 200
        assert [item["id"] for item in response.data["results"]] == [visible_meta.pk]

    def test_meta_detail_excludes_actions_outside_adt_territory(
        self, auth_client_adt_rn, municipio_rn, municipio_ce
    ):
        meta = WorkPlanMetaFactory(numero=1)
        visible_action = WorkPlanAcaoFactory(meta=meta, numero="1.1")
        hidden_action = WorkPlanAcaoFactory(meta=meta, numero="1.2")
        ActivityFactory(acao=visible_action, municipio=municipio_rn, status="concluido")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_adt_rn.get(f"/api/v1/metas/{meta.pk}/")

        assert response.status_code == 200
        assert [item["id"] for item in response.data["acoes"]] == [visible_action.pk]

    def test_articulador_lists_only_metas_with_actions_in_own_states(
        self, auth_client_articulador_rn, municipio_rn, municipio_ce
    ):
        visible_meta = WorkPlanMetaFactory(numero=1)
        hidden_meta = WorkPlanMetaFactory(numero=2)
        visible_action = WorkPlanAcaoFactory(meta=visible_meta, numero="1.1")
        hidden_action = WorkPlanAcaoFactory(meta=hidden_meta, numero="2.1")
        ActivityFactory(acao=visible_action, municipio=municipio_rn, status="concluido")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_articulador_rn.get("/api/v1/metas/")

        assert response.status_code == 200
        assert [item["id"] for item in response.data["results"]] == [visible_meta.pk]

    def test_ugp_can_update(self, auth_client, meta):
        response = auth_client.patch(
            f"/api/v1/metas/{meta.pk}/",
            {"titulo": "Atualizado"}, format="json",
        )
        assert response.status_code == 200
        assert response.data["titulo"] == "Atualizado"

    def test_adt_cannot_update(self, auth_client_adt_rn, meta):
        assert auth_client_adt_rn.patch(
            f"/api/v1/metas/{meta.pk}/",
            {"titulo": "Hack"}, format="json",
        ).status_code == 403


class TestMetaStatusCalculado:
    def test_no_prazo_when_no_acoes(self, meta):
        assert meta.status_calculado == "no_prazo"

    def test_concluida_when_all_acoes_concluidas(self, meta):
        acao1 = WorkPlanAcaoFactory(meta=meta, numero="1.1", quantidade_planejada=Decimal("2"))
        ActivityFactory(acao=acao1, status="concluido")
        ActivityFactory(acao=acao1, status="concluido")
        acao2 = WorkPlanAcaoFactory(meta=meta, numero="1.2", quantidade_planejada=Decimal("1"))
        ActivityFactory(acao=acao2, status="concluido")
        assert meta.status_calculado == "concluida"

    def test_em_atraso_when_past_and_pending(self, meta):
        meta.data_fim = date.today() - timedelta(days=1)
        meta.save(update_fields=["data_fim"])
        acao1 = WorkPlanAcaoFactory(meta=meta, numero="1.1", quantidade_planejada=Decimal("1"))
        ActivityFactory(acao=acao1, status="concluido")
        acao2 = WorkPlanAcaoFactory(meta=meta, numero="1.2", quantidade_planejada=Decimal("1"))
        assert meta.status_calculado == "em_atraso"

    def test_no_prazo_when_future_and_pending(self, meta):
        meta.data_fim = date.today() + timedelta(days=365)
        meta.save(update_fields=["data_fim"])
        acao1 = WorkPlanAcaoFactory(meta=meta, numero="1.1", quantidade_planejada=Decimal("1"))
        ActivityFactory(acao=acao1, status="concluido")
        acao2 = WorkPlanAcaoFactory(meta=meta, numero="1.2", quantidade_planejada=Decimal("1"))
        assert meta.status_calculado == "no_prazo"


class TestMetaValorTotalPlanejado:
    def test_zero_when_no_acoes(self, meta):
        assert meta.valor_total_planejado == 0

    def test_sums_acoes(self, meta):
        WorkPlanAcaoFactory(
            meta=meta, numero="1.1",
            quantidade_planejada=Decimal("100"),
            valor_unitario=Decimal("500"),
        )
        WorkPlanAcaoFactory(
            meta=meta, numero="1.2",
            quantidade_planejada=Decimal("60"),
            valor_unitario=Decimal("500"),
        )
        assert meta.valor_total_planejado == Decimal("80000.00")


class TestMetaExclusao:
    def test_delete_without_acoes_succeeds(self, auth_client, meta):
        assert auth_client.delete(f"/api/v1/metas/{meta.pk}/").status_code == 204
        assert not WorkPlanMeta.objects.filter(pk=meta.pk).exists()

    def test_delete_with_acoes_returns_400(self, auth_client, meta):
        WorkPlanAcaoFactory(meta=meta, numero="1.1")
        response = auth_client.delete(f"/api/v1/metas/{meta.pk}/")
        assert response.status_code == 400
        assert "Ações vinculadas" in response.data["detail"]
        assert WorkPlanMeta.objects.filter(pk=meta.pk).exists()


class TestMetaListagemDetalhe:
    def test_list_returns_200(self, auth_client, meta):
        response = auth_client.get("/api/v1/metas/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_detail_returns_200(self, auth_client, meta):
        response = auth_client.get(f"/api/v1/metas/{meta.pk}/")
        assert response.status_code == 200
        assert response.data["numero"] == 1
        assert "acoes" in response.data

    def test_list_filter_by_numero(self, auth_client, meta):
        WorkPlanMetaFactory(numero=3, titulo="Outra")
        response = auth_client.get("/api/v1/metas/?numero=1")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["numero"] == 1


# ===================================================================
#  ISSUE #135 — AÇÃO
# ===================================================================

class TestAcaoCriacao:
    def test_create_acao(self, auth_client, acao_payload):
        response = auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        assert response.status_code == 201
        assert response.data["numero"] == "1.1"
        assert response.data["descricao"] == "Ação de teste"

    def test_create_acao_auto_valor_total(self, auth_client, acao_payload):
        response = auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        assert response.status_code == 201
        assert Decimal(response.data["valor_total"]) == Decimal("50000.00")

    def test_create_acao_status_execucao_default(self, auth_client, acao_payload):
        response = auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        assert response.status_code == 201
        assert response.data["status_execucao"] == "no_prazo"

    def test_quantidade_realizada_read_only(self, auth_client, acao_payload):
        response = auth_client.post(
            "/api/v1/acoes/", {**acao_payload, "quantidade_realizada": "999"}, format="json"
        )
        assert response.status_code == 201
        assert response.data["quantidade_realizada"] == "0.00"


class TestAcaoNumeroFormato:
    def test_invalid_format_returns_400(self, auth_client, acao_payload):
        response = auth_client.post(
            "/api/v1/acoes/", {**acao_payload, "numero": "1"}, format="json"
        )
        assert response.status_code == 400
        assert "numero" in response.data

    def test_invalid_format_abc_returns_400(self, auth_client, acao_payload):
        response = auth_client.post(
            "/api/v1/acoes/", {**acao_payload, "numero": "abc"}, format="json"
        )
        assert response.status_code == 400

    def test_valid_formats_accepted(self, auth_client, meta):
        for num in ["1.1", "2.10", "7.99"]:
            payload = {
                "meta": meta.pk,
                "numero": num,
                "descricao": f"Ação {num}",
                "tipo_unidade": 11,
                "quantidade_planejada": "10.00",
                "valor_unitario": "100.00",
            }
            response = auth_client.post("/api/v1/acoes/", payload, format="json")
            assert response.status_code == 201, f"numero={num} falhou: {response.data}"


class TestAcaoUnicidadeNumero:
    def test_duplicate_within_same_meta_returns_400(self, auth_client, acao_payload):
        auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        response = auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        assert response.status_code == 400
        assert "numero" in response.data

    def test_same_numero_different_meta_allowed(self, auth_client, acao_payload, meta):
        auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        meta2 = WorkPlanMetaFactory(numero=3, titulo="Outra Meta")
        payload2 = {**acao_payload, "meta": meta2.pk}
        response = auth_client.post("/api/v1/acoes/", payload2, format="json")
        assert response.status_code == 201


class TestAcaoValorTotalCalculado:
    def test_valor_total_on_create(self, auth_client, acao_payload):
        response = auth_client.post("/api/v1/acoes/", acao_payload, format="json")
        assert Decimal(response.data["valor_total"]) == Decimal("100.00") * Decimal("500.00")

    def test_valor_total_updates_on_change(self, auth_client, acao, meta):
        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/",
            {"quantidade_planejada": "200.00", "valor_unitario": "1000.00"},
            format="json",
        )
        assert response.status_code == 200
        assert Decimal(response.data["valor_total"]) == Decimal("200000.00")


class TestAcaoQuantidadeRealizada:
    def test_counts_concluido_activities(self, acao):
        ActivityFactory(acao=acao, status="concluido")
        ActivityFactory(acao=acao, status="concluido")
        ActivityFactory(acao=acao, status="concluido")
        assert acao.quantidade_realizada == 3

    def test_ignores_non_concluido_activities(self, acao):
        ActivityFactory(acao=acao, status="planejado")
        ActivityFactory(acao=acao, status="agendado")
        ActivityFactory(acao=acao, status="concluido")
        assert acao.quantidade_realizada == 1

    def test_zero_when_no_activities(self, acao):
        assert acao.quantidade_realizada == 0


class TestAcaoStatusExecucao:
    def test_concluida_when_quantidade_atingida(self, acao):
        acao.quantidade_planejada = Decimal("2")
        ActivityFactory(acao=acao, status="concluido")
        ActivityFactory(acao=acao, status="concluido")
        assert acao.status_execucao == "concluida"

    def test_em_atraso_when_past_and_not_atingida(self, acao):
        acao.data_fim = date.today() - timedelta(days=1)
        acao.quantidade_planejada = Decimal("2")
        ActivityFactory(acao=acao, status="concluido")
        assert acao.status_execucao == "em_atraso"

    def test_no_prazo_when_future_and_not_atingida(self, acao):
        acao.data_fim = date.today() + timedelta(days=365)
        acao.quantidade_planejada = Decimal("2")
        ActivityFactory(acao=acao, status="concluido")
        assert acao.status_execucao == "no_prazo"


class TestAcaoPermissoes:
    def test_ugp_can_create(self, auth_client, acao_payload):
        assert auth_client.post(
            "/api/v1/acoes/", acao_payload, format="json"
        ).status_code == 201

    def test_super_admin_can_create(self, auth_client_super_admin, acao_payload):
        assert auth_client_super_admin.post(
            "/api/v1/acoes/", acao_payload, format="json"
        ).status_code == 201

    def test_adt_cannot_create(self, auth_client_adt_rn, acao_payload):
        assert auth_client_adt_rn.post(
            "/api/v1/acoes/", acao_payload, format="json"
        ).status_code == 403

    def test_agricultor_cannot_create(self, auth_client_sem_acesso, acao_payload):
        assert auth_client_sem_acesso.post(
            "/api/v1/acoes/", acao_payload, format="json"
        ).status_code == 403

    def test_any_authenticated_can_list(self, auth_client_adt_rn, acao):
        assert auth_client_adt_rn.get("/api/v1/acoes/").status_code == 200

    def test_adt_lists_only_actions_in_own_territory(
        self, auth_client_adt_rn, meta, municipio_rn, municipio_ce
    ):
        visible_action = WorkPlanAcaoFactory(meta=meta, numero="1.1")
        hidden_action = WorkPlanAcaoFactory(meta=meta, numero="1.2")
        ActivityFactory(acao=visible_action, municipio=municipio_rn, status="concluido")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_adt_rn.get("/api/v1/acoes/")

        assert response.status_code == 200
        assert [item["id"] for item in response.data["results"]] == [visible_action.pk]

    def test_articulador_lists_only_actions_in_own_states(
        self, auth_client_articulador_rn, meta, municipio_rn, municipio_ce
    ):
        visible_action = WorkPlanAcaoFactory(meta=meta, numero="1.1")
        hidden_action = WorkPlanAcaoFactory(meta=meta, numero="1.2")
        ActivityFactory(acao=visible_action, municipio=municipio_rn, status="concluido")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_articulador_rn.get("/api/v1/acoes/")

        assert response.status_code == 200
        assert [item["id"] for item in response.data["results"]] == [visible_action.pk]

    def test_adt_cannot_retrieve_action_from_another_territory(
        self, auth_client_adt_rn, meta, municipio_ce
    ):
        hidden_action = WorkPlanAcaoFactory(meta=meta, numero="1.1")
        ActivityFactory(acao=hidden_action, municipio=municipio_ce, status="concluido")

        response = auth_client_adt_rn.get(f"/api/v1/acoes/{hidden_action.pk}/")

        assert response.status_code == 404

    def test_filter_by_meta(self, auth_client, acao, meta):
        meta2 = WorkPlanMetaFactory(numero=3, titulo="Outra")
        WorkPlanAcaoFactory(meta=meta2, numero="3.1")
        response = auth_client.get(f"/api/v1/acoes/?meta={meta.pk}")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["meta"] == meta.pk


class TestAcaoExclusao:
    def test_delete_without_activities_succeeds(self, auth_client, acao):
        assert auth_client.delete(f"/api/v1/acoes/{acao.pk}/").status_code == 204
        assert not WorkPlanAcao.objects.filter(pk=acao.pk).exists()

    def test_delete_blocked_when_activities_exist(self, auth_client, meta):
        """Quando o model Activity existir (Sprint 8), o DELETE será bloqueado.
        Este teste valida que o endpoint funciona sem erros."""
        acao = WorkPlanAcaoFactory(meta=meta, numero="1.1")
        response = auth_client.delete(f"/api/v1/acoes/{acao.pk}/")
        assert response.status_code == 204


class TestAcaoListagemDetalhe:
    def test_list_returns_200(self, auth_client, acao):
        response = auth_client.get("/api/v1/acoes/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_detail_returns_200(self, auth_client, acao):
        response = auth_client.get(f"/api/v1/acoes/{acao.pk}/")
        assert response.status_code == 200
        assert response.data["numero"] == acao.numero
