"""
Testes dos endpoints administrativos SCA (#194):

- GET  /api/v1/sca/devices/
- GET  /api/v1/sca/sync-events/ (+ detalhe)
- GET  /api/v1/sca/conflicts/ (+ detalhe, POST resolver)
- Badge "Registrado via SCA" (ultima_origem / ultimo_sync_em)
- Filtro e anotação do UserViewSet (#160)
"""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.models import AuditLog
from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sca.tests.conftest import payload_upf
from apps.sca.tests.factories import (
    ConflictLogFactory,
    SyncDeviceFactory,
    SyncEventFactory,
)
from apps.sca.tests.test_sync_push import build_item, post_batch


# ──────────────────────────────────────────────────────────────
# Fixtures locais
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def ugp_user(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="Usuário UGP", profiles=[(role, None)])


@pytest.fixture
def auth_client_ugp(api_client, ugp_user):
    api_client.force_authenticate(user=ugp_user)
    return api_client


@pytest.fixture
def tecnico_ce(db, role_adt, outro_territory):
    return UserFactory(
        email="tecnico.ce@test.com", nome="Técnico CE", profiles=[(role_adt, outro_territory)]
    )


@pytest.fixture
def tecnico_global(db, role_adt):
    return UserFactory(
        email="tecnico.global@test.com", nome="Técnico Global", profiles=[(role_adt, None)]
    )


@pytest.fixture
def articulador_ce(db, outro_territory):
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    return UserFactory(
        email="articulador.ce@test.com",
        nome="Articulador CE",
        profiles=[(role, outro_territory)],
    )


@pytest.fixture
def upf_existente(db, municipio, projeto):
    from apps.sgp.tests.factories import UPFFactory

    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    upf.uuid_local = uuid4()
    upf.save(update_fields=["uuid_local"])
    return upf


def _device(user, device_id):
    return SyncDeviceFactory(user=user, device_id=device_id)


# ──────────────────────────────────────────────────────────────
# GET /api/v1/sca/devices/
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDevicesEndpoint:
    def _list(self, client, **params):
        return client.get("/api/v1/sca/devices/", data=params)

    def test_campos_do_item(self, auth_client_super_admin, usuario):
        device = _device(usuario, "dev-rn-1")
        response = self._list(auth_client_super_admin)

        assert response.status_code == 200
        assert response.data["limiar_alerta_dias"] == 7  # seedado pela migração core.0018
        item = next(i for i in response.data["results"] if i["id"] == device.pk)
        assert item["device_id"] == "dev-rn-1"
        assert item["tecnico"] == {
            "id": usuario.pk,
            "nome": usuario.nome,
            "email": usuario.email,
        }
        assert isinstance(item["registros_pendentes"], int)
        assert item["ativo"] is True

    def test_territorios_um_territorio(self, auth_client_super_admin, usuario, territory):
        device = _device(usuario, "dev-rn-1")
        item = next(
            i for i in self._list(auth_client_super_admin).data["results"] if i["id"] == device.pk
        )
        assert [t["id"] for t in item["territorios"]] == [territory.id]

    def test_territorios_varios(self, auth_client_super_admin, role_adt, territory, outro_territory):
        multi = UserFactory(
            email="multi@test.com",
            nome="Multi Território",
            profiles=[(role_adt, territory), (role_adt, outro_territory)],
        )
        device = _device(multi, "dev-multi")
        item = next(
            i for i in self._list(auth_client_super_admin).data["results"] if i["id"] == device.pk
        )
        assert sorted(t["id"] for t in item["territorios"]) == sorted(
            [territory.id, outro_territory.id]
        )

    def test_territorios_acesso_global(self, auth_client_super_admin, tecnico_global,
                                       territory, outro_territory):
        device = _device(tecnico_global, "dev-global")
        item = next(
            i for i in self._list(auth_client_super_admin).data["results"] if i["id"] == device.pk
        )
        assert sorted(t["id"] for t in item["territorios"]) == sorted(
            [territory.id, outro_territory.id]
        )

    def test_nao_expoe_status_conexao(self, auth_client_super_admin, usuario):
        _device(usuario, "dev-rn-1")
        items = self._list(auth_client_super_admin).data["results"]
        assert items
        assert all("status_conexao" not in i for i in items)

    def test_filtro_por_territorio_inclui_acesso_global(
        self, auth_client_super_admin, usuario, tecnico_ce, tecnico_global, territory
    ):
        dev_rn = _device(usuario, "dev-rn-1")
        _device(tecnico_ce, "dev-ce-1")
        dev_global = _device(tecnico_global, "dev-global")

        ids = {i["id"] for i in self._list(auth_client_super_admin, territorio=territory.id).data["results"]}
        assert ids == {dev_rn.pk, dev_global.pk}

    def test_filtro_por_tecnico(self, auth_client_super_admin, usuario, tecnico_ce):
        dev_rn = _device(usuario, "dev-rn-1")
        _device(tecnico_ce, "dev-ce-1")

        ids = {i["id"] for i in self._list(auth_client_super_admin, tecnico=usuario.pk).data["results"]}
        assert ids == {dev_rn.pk}

    def test_ordenacao_mais_parados_primeiro(self, auth_client_super_admin, usuario,
                                             tecnico_global):
        dev_recente = _device(usuario, "dev-recente")
        dev_antigo = _device(tecnico_global, "dev-antigo")
        SyncDevice.objects.filter(pk=dev_recente.pk).update(ultimo_pull_em=timezone.now())
        SyncDevice.objects.filter(pk=dev_antigo.pk).update(
            ultimo_push_em=timezone.now() - timedelta(days=30)
        )

        ordem = [
            (i["id"], i["ultimo_sync_servidor"])
            for i in self._list(auth_client_super_admin).data["results"]
        ]
        ids = [pk for pk, _ in ordem]
        assert ids.index(dev_antigo.pk) < ids.index(dev_recente.pk)
        # dispositivo que só deu pull não fica com ultimo_sync nulo (Coalesce/Greatest)
        antigo = next(v for pk, v in ordem if pk == dev_antigo.pk)
        assert antigo is not None

    def test_ugp_lista_e_articulador_recebe_403(self, auth_client_ugp, api_client,
                                                articulador, usuario):
        _device(usuario, "dev-rn-1")
        assert auth_client_ugp.get("/api/v1/sca/devices/").status_code == 200

        api_client.force_authenticate(user=articulador)
        assert api_client.get("/api/v1/sca/devices/").status_code == 403


# ──────────────────────────────────────────────────────────────
# Push → SyncEvent com contagens/erros/tipo_conexao (#157)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSyncEventFieldsFromPush:
    def test_push_preenche_contagens_e_erros_detalhes(self, auth_client, municipio, projeto):
        valido = build_item(payload=payload_upf(projeto, municipio))
        invalido = build_item(entidade="entidade_inexistente", payload={})

        response = auth_client.post(
            "/api/v1/sca/sync/push/",
            data={"registros": [valido, invalido], "device_id": "dev-001"},
            format="json",
            HTTP_X_CONNECTION_TYPE="wifi",
        )

        assert response.status_code == 200
        evento = SyncEvent.objects.order_by("-finalizado_em").first()
        assert evento.tipo == SyncEvent.Tipo.PUSH
        assert evento.contagem_enviados == 2
        assert evento.contagem_recebidos == 0
        assert evento.contagem_erros == 1
        assert evento.tipo_conexao == "wifi"
        assert evento.iniciado_em is not None
        assert evento.finalizado_em is not None
        (erro,) = evento.erros_detalhes
        assert set(erro.keys()) == {"uuid_local", "entidade", "mensagem", "codigo"}
        assert erro["entidade"] == "entidade_inexistente"

    def test_sem_header_tipo_conexao_fica_null(self, auth_client, municipio, projeto):
        post_batch(auth_client, [build_item(payload=payload_upf(projeto, municipio))])
        evento = SyncEvent.objects.order_by("-finalizado_em").first()
        assert evento.tipo_conexao is None


# ──────────────────────────────────────────────────────────────
# GET /api/v1/sca/sync-events/
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSyncEventsEndpoint:
    def test_historico_por_device_ordenado(self, auth_client_super_admin, usuario):
        device_a = _device(usuario, "dev-a")
        device_b = _device(usuario, "dev-b")

        antigo = SyncEventFactory(
            user=usuario, device=device_a, tipo=SyncEvent.Tipo.PULL,
            iniciado_em=timezone.now() - timedelta(hours=3),
        )
        novo = SyncEventFactory(
            user=usuario, device=device_a, tipo=SyncEvent.Tipo.PUSH,
            iniciado_em=timezone.now() - timedelta(hours=1),
        )
        SyncEventFactory(
            user=usuario, device=device_b, tipo=SyncEvent.Tipo.PUSH,
            iniciado_em=timezone.now(),
        )

        response = auth_client_super_admin.get(
            "/api/v1/sca/sync-events/", data={"device": device_a.pk}
        )
        assert response.status_code == 200
        ids = [e["id"] for e in response.data["results"]]
        assert ids == [novo.pk, antigo.pk]

    def test_filtros(self, auth_client_super_admin, usuario):
        SyncEventFactory(
            user=usuario, contagem_erros=0, iniciado_em=timezone.now() - timedelta(hours=2)
        )
        com_erro = SyncEventFactory(
            user=usuario,
            contagem_erros=2,
            erros_detalhes=[
                {"uuid_local": "u1", "entidade": "upf", "mensagem": "boom", "codigo": "ERRO"},
            ],
            iniciado_em=timezone.now(),
        )

        response = auth_client_super_admin.get(
            "/api/v1/sca/sync-events/", data={"com_erro": "true"}
        )
        assert response.status_code == 200
        assert [e["id"] for e in response.data["results"]] == [com_erro.pk]

    def test_listagem_oculta_erros_detalhes_detalhe_exibe(self, auth_client_super_admin, usuario):
        evento = SyncEventFactory(
            user=usuario,
            contagem_erros=2,
            erros_detalhes=[
                {"uuid_local": "u1", "entidade": "upf", "mensagem": "boom", "codigo": "ERRO"},
                {"uuid_local": "u2", "entidade": "upf", "mensagem": "pow", "codigo": "ERRO"},
            ],
            iniciado_em=timezone.now(),
        )

        listado = auth_client_super_admin.get("/api/v1/sca/sync-events/").data["results"][0]
        assert listado["has_erros"] is True
        assert listado["contagem_erros"] == 2
        assert "erros_detalhes" not in listado
        assert listado["tecnico"]["email"] == usuario.email
        assert listado["dispositivo"]["device_id"]

        detalhe = auth_client_super_admin.get(f"/api/v1/sca/sync-events/{evento.pk}/")
        assert detalhe.status_code == 200
        assert len(detalhe.data["erros_detalhes"]) == 2

    def test_articulador_estadual_recebe_403(self, api_client, articulador):
        api_client.force_authenticate(user=articulador)
        assert api_client.get("/api/v1/sca/sync-events/").status_code == 403


# ──────────────────────────────────────────────────────────────
# Conflitos: criação sensível/não-sensível + endpoints (#158)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestConflictResolution:
    def _conflito_pendente(self, upf, territorio, **overrides):
        defaults = dict(
            entidade="upf",
            uuid_local=str(upf.uuid_local),
            campo="whatsapp",
            valor_local="9999",
            valor_servidor="1111",
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS,
            campo_sensivel=False,
            status=ConflictLog.Status.PENDENTE,
            territorio=territorio,
        )
        defaults.update(overrides)
        return ConflictLogFactory(**defaults)

    def test_conflito_sensivel_fica_pendente_e_nao_aplica_valor(
        self, auth_client, articulador, upf_existente, municipio, projeto
    ):
        from apps.sgp.models import MembroFamilia

        upf = upf_existente
        MembroFamilia.objects.filter(pk=upf.titular.pk).update(cpf="52998224725")

        base = payload_upf(projeto, municipio)
        base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": "86288366757"}
        payload = dict(base)
        payload["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": "33355588800"}

        item = build_item(
            operacao="update",
            uuid_local=upf.uuid_local,
            payload=payload,
            base=base,
            updated_at=timezone.now() + timedelta(minutes=1),
        )

        with patch("apps.sca.tasks.notify_articulador_sync_conflict.delay"):
            response = post_batch(auth_client, [item])

        assert response.data["resultados"][0]["status"] == "conflito"
        conflito = ConflictLog.objects.get(campo="titular.cpf")
        assert conflito.status == ConflictLog.Status.PENDENTE
        upf.titular.refresh_from_db()
        assert upf.titular.cpf == "52998224725"  # estratégia automática não aplicada

    def test_resolver_decisao_local_aplica_valor_grava_metadata(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        conflito = self._conflito_pendente(upf_existente, territory)

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "local"},
            format="json",
        )

        assert response.status_code == 200
        upf_existente.refresh_from_db()
        assert upf_existente.whatsapp == "9999"

        conflito.refresh_from_db()
        assert conflito.status == ConflictLog.Status.RESOLVIDO_MANUAL
        assert conflito.valor_final == "9999"
        assert conflito.resolvido_por_id == super_admin_user.pk
        assert conflito.resolvido_em is not None
        assert AuditLog.objects.filter(acao="sca.conflict_resolved").exists()

    def test_resolver_decisao_manual_aplica_valor_manual(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        conflito = self._conflito_pendente(upf_existente, territory)

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "manual", "valor_manual": "7777"},
            format="json",
        )

        assert response.status_code == 200
        upf_existente.refresh_from_db()
        assert upf_existente.whatsapp == "7777"
        conflito.refresh_from_db()
        assert conflito.valor_final == "7777"
        assert conflito.resolvido_por == super_admin_user

    def test_resolver_ja_resolvido_retorna_409(
        self, auth_client_super_admin, upf_existente, territory
    ):
        conflito = self._conflito_pendente(
            upf_existente, territory, status=ConflictLog.Status.RESOLVIDO_MANUAL
        )

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "servidor"},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["code"] == "CONFLITO_JA_RESOLVIDO"

    def test_isolamento_estadual_listagem_e_resolucao(
        self, api_client, auth_client_super_admin, articulador, articulador_ce,
        upf_existente, territory, outro_territory,
    ):
        conflito_rn = self._conflito_pendente(upf_existente, territory)
        conflito_ce = self._conflito_pendente(upf_existente, outro_territory)

        api_client.force_authenticate(user=articulador)
        ids_rn = {c["id"] for c in api_client.get("/api/v1/sca/conflicts/").data["results"]}
        assert ids_rn == {conflito_rn.pk}

        api_client.force_authenticate(user=articulador_ce)
        ids_ce = {c["id"] for c in api_client.get("/api/v1/sca/conflicts/").data["results"]}
        assert ids_ce == {conflito_ce.pk}

        # conflito de outro estado nem é visível para resolução (queryset escopado)
        resposta_fora = api_client.post(
            f"/api/v1/sca/conflicts/{conflito_rn.pk}/resolver/",
            data={"decisao": "local"},
            format="json",
        )
        assert resposta_fora.status_code in (403, 404)

        todos = auth_client_super_admin.get("/api/v1/sca/conflicts/")
        assert {c["id"] for c in todos.data["results"]} == {conflito_rn.pk, conflito_ce.pk}

    def test_detalhe_trae_snapshot_registro_atual(
        self, auth_client_super_admin, upf_existente, territory
    ):
        conflito = self._conflito_pendente(upf_existente, territory)

        response = auth_client_super_admin.get(f"/api/v1/sca/conflicts/{conflito.pk}/")

        assert response.status_code == 200
        assert response.data["registro_atual"] is not None
        assert response.data["registro_atual"]["id"] == upf_existente.pk

    def test_filtro_status_na_listagem(
        self, auth_client_super_admin, upf_existente, territory, outro_territory
    ):
        pendente = self._conflito_pendente(upf_existente, territory)
        self._conflito_pendente(
            upf_existente, outro_territory, status=ConflictLog.Status.RESOLVIDO_AUTO
        )

        ids = {
            c["id"]
            for c in auth_client_super_admin.get(
                "/api/v1/sca/conflicts/", data={"status": "pendente"}
            ).data["results"]
        }
        assert ids == {pendente.pk}


# ──────────────────────────────────────────────────────────────
# Badge "Registrado via SCA" (#159)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBadgeUltimaOrigem:
    def test_web_entao_sca_entao_web(self, auth_client, auth_client_super_admin,
                                     upf_existente, municipio, projeto):
        upf = upf_existente
        assert upf.ultima_origem == "web"
        assert upf.ultimo_sync_em is None

        # edição via app SCA (push LWW cliente vence)
        base = payload_upf(projeto, municipio)
        base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": upf.titular.cpf}
        payload = dict(base)
        payload["whatsapp"] = "9999"
        item = build_item(
            operacao="update",
            uuid_local=upf.uuid_local,
            payload=payload,
            base=base,
            updated_at=timezone.now() + timedelta(minutes=1),
        )
        response = post_batch(auth_client, [item])
        assert response.data["resultados"][0]["status"] == "ok"

        upf.refresh_from_db()
        assert upf.ultima_origem == "sca"
        assert upf.ultimo_sync_em is not None
        ultimo_sync_sca = upf.ultimo_sync_em

        # edição via plataforma Web vira a badge, preservando o histórico de sync
        patch_response = auth_client_super_admin.patch(
            f"/api/v1/upfs/{upf.pk}/", data={"apelido": "Editada Web"}, format="json"
        )
        assert patch_response.status_code == 200
        upf.refresh_from_db()
        assert upf.ultima_origem == "web"
        assert upf.ultimo_sync_em == ultimo_sync_sca

    def test_serializer_detail_expoe_campos_badge(self, auth_client_super_admin, upf_existente):
        response = auth_client_super_admin.get(f"/api/v1/upfs/{upf_existente.pk}/")
        assert response.status_code == 200
        assert response.data["ultima_origem"] == "web"
        assert response.data["ultimo_sync_em"] is None
        assert response.data["device_id"] is None
        assert response.data["uuid_local"]


# ──────────────────────────────────────────────────────────────
# UserViewSet — filtro com_dispositivo e campos revogação (#160)
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserViewSetIssue160:
    def test_filtro_com_dispositivo_true(self, auth_client_super_admin, usuario, tecnico_ce):
        _device(usuario, "dev-rn-1")

        response = auth_client_super_admin.get(
            "/api/v1/users/", data={"com_dispositivo": "true"}
        )
        emails = {u["email"] for u in response.data["results"]}
        assert emails == {usuario.email}

        item = response.data["results"][0]
        assert item["qtd_dispositivos"] == 1
        assert item["ultimo_sync_dispositivos"] is None  # device ainda sem sync

    def test_sem_filtro_nao_anota_mas_lista_todos(
        self, auth_client_super_admin, usuario, tecnico_ce
    ):
        _device(usuario, "dev-rn-1")

        response = auth_client_super_admin.get("/api/v1/users/")
        emails = {u["email"] for u in response.data["results"]}
        assert {usuario.email, tecnico_ce.email} <= emails
        assert all(u["qtd_dispositivos"] is None for u in response.data["results"])

    def test_serializers_expoem_dados_de_revogacao(self, auth_client_super_admin, usuario):
        revoke = auth_client_super_admin.patch(f"/api/v1/users/{usuario.pk}/revogar-acesso/")
        assert revoke.status_code == 200

        detalhe = auth_client_super_admin.get(f"/api/v1/users/{usuario.pk}/")
        assert detalhe.status_code == 200
        assert detalhe.data["acesso_revogado"] is True
        assert detalhe.data["acesso_revogado_em"] is not None
        assert detalhe.data["acesso_revogado_por"]["email"] == "super@admin.com"

        listado = auth_client_super_admin.get("/api/v1/users/").data["results"]
        alvo = next(u for u in listado if u["id"] == usuario.pk)
        assert alvo["acesso_revogado"] is True
        assert alvo["acesso_revogado_por"]["nome"]
        assert "email" not in alvo["acesso_revogado_por"]  # no list vai só {id, nome}
