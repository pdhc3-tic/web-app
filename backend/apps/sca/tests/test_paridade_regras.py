"""
Teste de paridade entre a API web (`apps/sgp`) e o sync SCA (Issue #277).

As duas portas de entrada escrevem nas mesmas entidades (Activity, Membro,
UPF) e devem aplicar exatamente as mesmas regras de negócio — transição de
status, evidência/justificativa/nova-data obrigatórias, unicidade global de
CPF e titular único por UPF — consumindo os mesmos serviços de domínio
(`apps.sgp.services.activity_status`, `apps.sgp.services.membro_rules`).

Reaproveita `build_item`/`post_batch` de `test_sync_push.py` para o lado
sync, e bate direto nos endpoints REST de `apps/sgp` para o lado web,
usando o `auth_client` (role `adt-acr` + território) de `conftest.py` — que
tem acesso de leitura/escrita normal em ambos os caminhos desde que os
registros usem o `municipio`/`projeto` das fixtures deste módulo.
"""

from uuid import uuid4

import pytest

from apps.sca.models import ConflictLog
from apps.sca.tests.test_sync_push import build_item, post_batch
from apps.sgp.models import MembroFamilia
from apps.sgp.tests.factories import ActivityFactory, MembroFactory, UPFFactory


def _activity_detail_url(pk):
    return f"/api/v1/sgp/atividades/{pk}/"


def _membro_list_url(upf_pk):
    return f"/api/v1/sgp/upfs/{upf_pk}/membros/"


def _membro_detail_url(upf_pk, membro_pk):
    return f"/api/v1/sgp/upfs/{upf_pk}/membros/{membro_pk}/"


def _sync_update_activity(auth_client, atividade, payload):
    atividade.uuid_local = uuid4()
    atividade.save(update_fields=["uuid_local"])
    item = build_item(
        "activity",
        uuid_local=atividade.uuid_local,
        operacao="update",
        payload=payload,
        base={},
    )
    return post_batch(auth_client, [item]).data["resultados"][0]


# ---------------------------------------------------------------------------
# test_paridade_status_invalido
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_status_invalido(auth_client, municipio):
    atividade_web = ActivityFactory(municipio=municipio, status="planejado")
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk), {"status": "concluido"}, format="json"
    )
    assert response.status_code == 400
    atividade_web.refresh_from_db()
    assert atividade_web.status == "planejado"

    atividade_sync = ActivityFactory(municipio=municipio, status="planejado")
    resultado = _sync_update_activity(auth_client, atividade_sync, {"status": "concluido"})
    assert resultado["status"] == "erro"
    assert "TRANSICAO_INVALIDA" in resultado["erro"]
    atividade_sync.refresh_from_db()
    assert atividade_sync.status == "planejado"


# ---------------------------------------------------------------------------
# test_paridade_evidencia
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_evidencia(auth_client, municipio):
    atividade_web = ActivityFactory(municipio=municipio, status="em_andamento")
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk), {"status": "concluido"}, format="json"
    )
    assert response.status_code == 400
    atividade_web.refresh_from_db()
    assert atividade_web.status == "em_andamento"

    atividade_sync = ActivityFactory(municipio=municipio, status="em_andamento")
    resultado = _sync_update_activity(auth_client, atividade_sync, {"status": "concluido"})
    assert resultado["status"] == "erro"
    assert "EVIDENCIA_OBRIGATORIA" in resultado["erro"]
    atividade_sync.refresh_from_db()
    assert atividade_sync.status == "em_andamento"

    assert ConflictLog.objects.filter(
        entidade="activity",
        uuid_local=atividade_sync.uuid_local,
        estrategia=ConflictLog.Estrategia.REGRA_NEGOCIO_REJEITADA,
    ).exists()


# ---------------------------------------------------------------------------
# test_paridade_cpf_duplicado (via update — o create já era coberto pela
# Estratégia 1/DUPLICATA existente antes desta issue)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_cpf_duplicado(auth_client, municipio, projeto):
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk), {"cpf": cpf_ja_usado}, format="json"
    )
    assert response.status_code == 400
    membro_web.refresh_from_db()
    assert membro_web.cpf == ""

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    membro_sync = MembroFactory(upf=upf_sync, nome_completo="Alvo Sync", grau_parentesco="filho", cpf="")
    membro_sync.uuid_local = uuid4()
    membro_sync.save(update_fields=["uuid_local"])
    item = build_item(
        "member",
        uuid_local=membro_sync.uuid_local,
        operacao="update",
        payload={"cpf": cpf_ja_usado},
        base={},
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "CPF_DUPLICADO" in resultado["erro"]
    membro_sync.refresh_from_db()
    assert membro_sync.cpf == ""


# ---------------------------------------------------------------------------
# test_paridade_titular_unico
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_titular_unico(auth_client, municipio, projeto):
    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    response = auth_client.post(
        _membro_list_url(upf_web.pk),
        {"nome_completo": "Segundo Titular Web", "grau_parentesco": "titular", "cpf": "52998224725"},
        format="json",
    )
    assert response.status_code == 400
    assert MembroFamilia.objects.filter(upf=upf_web, grau_parentesco="titular").count() == 1

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    item = build_item(
        "member",
        operacao="create",
        payload={
            "upf": upf_sync.pk,
            "nome_completo": "Segundo Titular Sync",
            "grau_parentesco": "titular",
            "cpf": "04227503523",
        },
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "TITULAR_DUPLICADO" in resultado["erro"]
    assert MembroFamilia.objects.filter(upf=upf_sync, grau_parentesco="titular").count() == 1


# ---------------------------------------------------------------------------
# test_conflito_registrado
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_conflito_registrado(auth_client, municipio):
    atividade_ok = ActivityFactory(municipio=municipio, status="planejado")
    resultado_ok = _sync_update_activity(auth_client, atividade_ok, {"status": "agendado"})
    assert resultado_ok["status"] == "ok"
    assert ConflictLog.objects.filter(uuid_local=atividade_ok.uuid_local).count() == 0

    atividade_rejeitada = ActivityFactory(municipio=municipio, status="em_andamento")
    resultado_rejeitado = _sync_update_activity(
        auth_client, atividade_rejeitada, {"status": "concluido"}
    )
    assert resultado_rejeitado["status"] == "erro"

    conflito = ConflictLog.objects.get(
        entidade="activity", uuid_local=atividade_rejeitada.uuid_local
    )
    assert conflito.estrategia == ConflictLog.Estrategia.REGRA_NEGOCIO_REJEITADA
    assert conflito.status == ConflictLog.Status.PENDENTE
    assert conflito.campo


# ---------------------------------------------------------------------------
# test_matriz_de_paridade — formaliza "payload rejeitado pela API web é
# igualmente rejeitado (ou vira conflito) pelo sync"
# ---------------------------------------------------------------------------

CASOS_ACTIVITY = {
    "status_invalido": {
        "status_atual": "planejado",
        "payload": {"status": "concluido"},
        "sync_codigo": "TRANSICAO_INVALIDA",
    },
    "evidencia_ausente": {
        "status_atual": "em_andamento",
        "payload": {"status": "concluido"},
        "sync_codigo": "EVIDENCIA_OBRIGATORIA",
    },
    "justificativa_ausente": {
        "status_atual": "planejado",
        "payload": {"status": "cancelada"},
        "sync_codigo": "JUSTIFICATIVA_OBRIGATORIA",
    },
    "nova_data_ausente": {
        "status_atual": "adiada",
        "payload": {"status": "agendado"},
        "sync_codigo": "NOVA_DATA_OBRIGATORIA",
    },
}


def _caso_activity(cfg, auth_client, municipio, projeto):
    atividade_web = ActivityFactory(municipio=municipio, status=cfg["status_atual"])
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk), cfg["payload"], format="json"
    )
    rejeitado_web = response.status_code == 400

    atividade_sync = ActivityFactory(municipio=municipio, status=cfg["status_atual"])
    resultado = _sync_update_activity(auth_client, atividade_sync, cfg["payload"])
    rejeitado_sync = resultado["status"] == "erro"
    codigo_presente = cfg["sync_codigo"] in resultado["erro"]
    return rejeitado_web, rejeitado_sync, codigo_presente


def _caso_cpf_duplicado(auth_client, municipio, projeto):
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk), {"cpf": cpf_ja_usado}, format="json"
    )
    rejeitado_web = response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    membro_sync = MembroFactory(upf=upf_sync, nome_completo="Alvo Sync", grau_parentesco="filho", cpf="")
    membro_sync.uuid_local = uuid4()
    membro_sync.save(update_fields=["uuid_local"])
    item = build_item(
        "member",
        uuid_local=membro_sync.uuid_local,
        operacao="update",
        payload={"cpf": cpf_ja_usado},
        base={},
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    rejeitado_sync = resultado["status"] == "erro"
    codigo_presente = "CPF_DUPLICADO" in resultado["erro"]
    return rejeitado_web, rejeitado_sync, codigo_presente


def _caso_titular_duplicado(auth_client, municipio, projeto):
    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    response = auth_client.post(
        _membro_list_url(upf_web.pk),
        {"nome_completo": "Segundo Titular Web", "grau_parentesco": "titular", "cpf": "52998224725"},
        format="json",
    )
    rejeitado_web = response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    item = build_item(
        "member",
        operacao="create",
        payload={
            "upf": upf_sync.pk,
            "nome_completo": "Segundo Titular Sync",
            "grau_parentesco": "titular",
            "cpf": "04227503523",
        },
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    rejeitado_sync = resultado["status"] == "erro"
    codigo_presente = "TITULAR_DUPLICADO" in resultado["erro"]
    return rejeitado_web, rejeitado_sync, codigo_presente


CASOS_MATRIZ = {
    "status_invalido": lambda ac, mu, pr: _caso_activity(CASOS_ACTIVITY["status_invalido"], ac, mu, pr),
    "evidencia_ausente": lambda ac, mu, pr: _caso_activity(CASOS_ACTIVITY["evidencia_ausente"], ac, mu, pr),
    "justificativa_ausente": lambda ac, mu, pr: _caso_activity(CASOS_ACTIVITY["justificativa_ausente"], ac, mu, pr),
    "nova_data_ausente": lambda ac, mu, pr: _caso_activity(CASOS_ACTIVITY["nova_data_ausente"], ac, mu, pr),
    "cpf_duplicado": _caso_cpf_duplicado,
    "titular_duplicado": _caso_titular_duplicado,
}


@pytest.mark.django_db
@pytest.mark.parametrize("caso", CASOS_MATRIZ.keys())
def test_matriz_de_paridade(caso, auth_client, municipio, projeto):
    rejeitado_web, rejeitado_sync, codigo_presente = CASOS_MATRIZ[caso](auth_client, municipio, projeto)

    assert rejeitado_web is True, f"web deveria rejeitar o caso '{caso}'"
    assert rejeitado_sync is True, f"sync deveria rejeitar o caso '{caso}'"
    assert codigo_presente
    assert rejeitado_web == rejeitado_sync
