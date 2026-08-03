"""
Testes do endpoint POST /api/v1/sca/sync/push.

Cobre as 4 estratégias de conflito da seção 4 do SCA_Requisitos,
idempotência por uuid_local e isolamento territorial por item.
"""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sca.tests.conftest import payload_upf
from apps.sgp.models import UPF


def build_item(
    entidade="upf",
    *,
    uuid_local=None,
    operacao="create",
    payload=None,
    base=None,
    updated_at=None,
    device_id="dev-001",
):
    return {
        "entidade": entidade,
        "uuid_local": str(uuid_local or uuid4()),
        "operacao": operacao,
        "payload_json": payload or {},
        "base_json": base or {},
        "updated_at": (updated_at or timezone.now()).isoformat(),
        "device_id": device_id,
    }


def post_batch(auth_client, registros, device_id="dev-001"):
    return auth_client.post(
        "/api/v1/sca/sync/push/",
        data={"registros": registros, "device_id": device_id},
        format="json",
    )


# ---------------------------------------------------------------------------
# Registro novo válido → ok com id_servidor
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_upf_nova_retorna_ok_com_id_servidor(auth_client, usuario, municipio, projeto):
    item = build_item(payload=payload_upf(projeto, municipio))
    response = post_batch(auth_client, [item])

    assert response.status_code == 200
    resultado = response.data["resultados"][0]
    assert resultado["status"] == "ok"
    assert resultado["id_servidor"]
    assert resultado["uuid_local"] == item["uuid_local"]

    upf = UPF.objects.get(pk=resultado["id_servidor"])
    assert str(upf.uuid_local) == item["uuid_local"]
    assert upf.titular.nome_completo == "Maria da Silva"
    assert upf.territorio_id == municipio.territory_id
    assert response.data["sucesso"] == 1

    # device e evento registrados
    device = SyncDevice.objects.get(user=usuario, device_id="dev-001")
    assert device.ultimo_push_em is not None
    assert SyncEvent.objects.filter(user=usuario, tipo=SyncEvent.Tipo.PUSH).count() == 1


# ---------------------------------------------------------------------------
# Estratégia 1 — duplicata por identificador natural (CPF)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_duas_upfs_mesmo_cpf_em_erro_sem_duplicata(auth_client, municipio, projeto):
    cpf = "86288366757"
    item1 = build_item(payload=payload_upf(projeto, municipio, titular={"nome_completo": "Maria", "cpf": cpf}))
    item2 = build_item(payload=payload_upf(projeto, municipio, titular={"nome_completo": "João", "cpf": cpf}))

    response = post_batch(auth_client, [item1, item2])

    assert response.status_code == 200
    resultados = {r["uuid_local"]: r for r in response.data["resultados"]}
    assert resultados[item1["uuid_local"]]["status"] == "ok"
    assert resultados[item2["uuid_local"]]["status"] == "erro"
    assert "DUPLICATA" in resultados[item2["uuid_local"]]["erro"]

    assert UPF.objects.count() == 1
    assert ConflictLog.objects.filter(
        estrategia=ConflictLog.Estrategia.DUPLICATE_REJEITADO
    ).count() == 1


@pytest.mark.django_db
def test_push_upf_nova_vs_cpf_ja_existente_no_servidor(auth_client, municipio, projeto, upf_existente):
    item = build_item(payload=payload_upf(projeto, municipio, titular={"nome_completo": "Outro", "cpf": upf_existente.titular.cpf}))
    response = post_batch(auth_client, [item])

    assert response.status_code == 200
    resultado = response.data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "DUPLICATA" in resultado["erro"]
    assert UPF.objects.count() == 1


@pytest.fixture
def upf_existente(db, municipio, projeto):
    from apps.sgp.tests.factories import UPFFactory

    return UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")


# ---------------------------------------------------------------------------
# Estratégia 2 — campos diferentes (sem sobreposição) → merge automático
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_campos_diferentes_merge_sem_conflict_log(auth_client, upf_existente, municipio, projeto):
    upf = upf_existente
    upf.apelido = "B"  # alterado no servidor desde a última sincronização
    upf.save()

    base = payload_upf(projeto, municipio, apelido="A", whatsapp="")
    base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": upf.titular.cpf}
    payload = dict(base)
    payload["whatsapp"] = "84 9999-0000"  # alterado localmente (sem sobreposição)

    item = build_item(
        operacao="update",
        payload=payload,
        base=base,
        updated_at=timezone.now(),
    )
    response = post_batch(auth_client, [item])

    assert response.status_code == 200
    resultado = response.data["resultados"][0]
    assert resultado["status"] == "ok"

    upf.refresh_from_db()
    assert upf.apelido == "B"        # valor do servidor preservado
    assert upf.whatsapp == "84 9999-0000"  # merge do valor local
    assert ConflictLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Estratégia 3 — mesmo campo alterado em ambos → last-write-wins + conflict_log
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_mesmo_campo_sobreposicao_lww_client_novo(auth_client, upf_existente, municipio, projeto):
    upf = upf_existente
    upf.whatsapp = "1111"  # alterado no servidor
    upf.save()

    base = payload_upf(projeto, municipio, whatsapp="")
    base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": upf.titular.cpf}
    payload = dict(base)
    payload["whatsapp"] = "9999"  # alterado localmente

    item = build_item(
        operacao="update",
        payload=payload,
        base=base,
        updated_at=timezone.now() + timedelta(minutes=1),  # local mais recente
    )
    response = post_batch(auth_client, [item])

    assert response.status_code == 200
    resultado = response.data["resultados"][0]
    assert resultado["status"] == "conflito"

    upf.refresh_from_db()
    assert upf.whatsapp == "9999"

    conflito = ConflictLog.objects.get(campo="whatsapp")
    assert conflito.valor_local == "9999"
    assert conflito.valor_servidor == "1111"
    assert conflito.estrategia == ConflictLog.Estrategia.LAST_WRITE_WINS


@pytest.mark.django_db
def test_push_mesmo_campo_lww_servidor_novo(auth_client, upf_existente, municipio, projeto):
    upf = upf_existente
    upf.whatsapp = "1111"
    upf.save()

    base = payload_upf(projeto, municipio, whatsapp="")
    base["titular"] = {"nome_completo": upf.titular.nome_completo, "cpf": upf.titular.cpf}
    payload = dict(base)
    payload["whatsapp"] = "9999"

    item = build_item(
        operacao="update",
        payload=payload,
        base=base,
        updated_at=timezone.now() - timedelta(minutes=2),  # servidor mais recente
    )
    response = post_batch(auth_client, [item])

    assert response.status_code == 200
    assert response.data["resultados"][0]["status"] == "conflito"

    upf.refresh_from_db()
    assert upf.whatsapp == "1111"  # servidor prevalece
    assert ConflictLog.objects.filter(campo="whatsapp").count() == 1


# ---------------------------------------------------------------------------
# Estratégia 4 — excluído no servidor, modificado offline
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_excluido_no_servidor_descarta_e_notifica(auth_client, upf_inativa, municipio, projeto):
    upf = upf_inativa
    payload = payload_upf(projeto, municipio, whatsapp="local editado")

    item = build_item(
        operacao="update",
        uuid_local=upf.uuid_local or uuid4(),
        payload=payload,
        base={},
        updated_at=timezone.now(),
    )

    with patch("apps.sca.tasks.notify_tecnico_sync_discard.delay") as mock_notify:
        response = post_batch(auth_client, [item])

    assert response.status_code == 200
    resultado = response.data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "EXCLUIDO_NO_SERVIDOR" in resultado["erro"]
    mock_notify.assert_called_once()

    # exclusão prevalece: registro permanece inativo e sem a alteração local
    upf.refresh_from_db()
    assert upf.ativa is False
    assert upf.whatsapp != "local editado"

    assert ConflictLog.objects.filter(
        estrategia=ConflictLog.Estrategia.EXCLUSAO_PREVALECE
    ).exists()


@pytest.fixture
def upf_inativa(db, municipio, projeto):
    from apps.sgp.tests.factories import UPFFactory

    upf = UPFFactory(municipio=municipio, projeto=projeto, ativa=False, titular_cpf="11144477735")
    upf.uuid_local = uuid4()
    upf.save(update_fields=["uuid_local"])
    return upf


# ---------------------------------------------------------------------------
# Conflito em campo sensível (CPF) → notifica Articulador Estadual (Celery)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_conflito_campo_sensivel_notifica_articulador(auth_client, articulador, upf_existente, municipio, projeto):
    upf = upf_existente
    upf.uuid_local = uuid4()
    upf.save(update_fields=["uuid_local"])
    MembroFamilia = upf.titular.__class__
    MembroFamilia.objects.filter(pk=upf.titular.pk).update(cpf="52998224725")  # servidor alterou o CPF

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

    with patch("apps.sca.tasks.notify_articulador_sync_conflict.delay") as mock_notify:
        response = post_batch(auth_client, [item])

    assert response.status_code == 200
    assert response.data["resultados"][0]["status"] == "conflito"
    mock_notify.assert_called_once()

    conflito = ConflictLog.objects.get(campo="titular.cpf")
    assert conflito.campo_sensivel is True
    assert conflito.valor_servidor == "52998224725"
    assert conflito.valor_local == "33355588800"

    upf.titular.refresh_from_db()
    assert upf.titular.cpf == "33355588800"


# ---------------------------------------------------------------------------
# Idempotência por uuid_local
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_idempotente_mesmo_uuid_nao_duplica(auth_client, municipio, projeto):
    item = build_item(payload=payload_upf(projeto, municipio))

    first = post_batch(auth_client, [item])
    assert first.data["resultados"][0]["status"] == "ok"
    id_servidor = first.data["resultados"][0]["id_servidor"]

    second = post_batch(auth_client, [item])  # reenvio (ex: queda de conexão)
    assert second.status_code == 200
    resultado = second.data["resultados"][0]
    assert resultado["status"] == "ok"
    assert resultado["id_servidor"] == id_servidor

    assert UPF.objects.count() == 1


# ---------------------------------------------------------------------------
# Isolamento territorial — item fora do escopo não interrompe o batch
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_push_item_fora_do_territorio_erro_por_item(auth_client, municipio, municipio_outro, projeto):
    item_ok = build_item(payload=payload_upf(projeto, municipio))
    item_fora = build_item(payload=payload_upf(projeto, municipio_outro))

    response = post_batch(auth_client, [item_ok, item_fora])

    assert response.status_code == 200
    resultados = {r["uuid_local"]: r for r in response.data["resultados"]}

    assert resultados[item_ok["uuid_local"]]["status"] == "ok"
    assert resultados[item_fora["uuid_local"]]["status"] == "erro"
    assert "FORA_TERRITORIO" in resultados[item_fora["uuid_local"]]["erro"]

    assert UPF.objects.count() == 1  # apenas o item válido foi persistido
