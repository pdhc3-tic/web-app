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

from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.sca.models import ConflictLog
from apps.sca.tests.conftest import payload_upf
from apps.sca.tests.test_sync_push import build_item, post_batch
from apps.sgp.models import MembroFamilia
from apps.sgp.services.membro_rules import normalizar_cpf
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
# Cenários adicionais levantados na revisão do PR #304 (Issue #277)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_cpf_formatado(auth_client, municipio, projeto):
    """CPF com máscara deve ser normalizado e detectado como duplicata nos
    dois caminhos — não só quando chega já só com dígitos."""
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )
    cpf_formatado = "862.883.667-57"

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk), {"cpf": cpf_formatado}, format="json"
    )
    assert response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    membro_sync = MembroFactory(upf=upf_sync, nome_completo="Alvo Sync", grau_parentesco="filho", cpf="")
    membro_sync.uuid_local = uuid4()
    membro_sync.save(update_fields=["uuid_local"])
    item = build_item(
        "member",
        uuid_local=membro_sync.uuid_local,
        operacao="update",
        payload={"cpf": cpf_formatado},
        base={},
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "CPF_DUPLICADO" in resultado["erro"]
    membro_sync.refresh_from_db()
    assert membro_sync.cpf == ""


@pytest.mark.django_db
def test_paridade_cpf_invalido(auth_client, municipio, projeto):
    """Dígito verificador errado é rejeitado nos dois caminhos."""
    cpf_invalido = "11111111111"

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk), {"cpf": cpf_invalido}, format="json"
    )
    assert response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    membro_sync = MembroFactory(upf=upf_sync, nome_completo="Alvo Sync", grau_parentesco="filho", cpf="")
    membro_sync.uuid_local = uuid4()
    membro_sync.save(update_fields=["uuid_local"])
    item = build_item(
        "member",
        uuid_local=membro_sync.uuid_local,
        operacao="update",
        payload={"cpf": cpf_invalido},
        base={},
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "CPF_INVALIDO" in resultado["erro"]
    membro_sync.refresh_from_db()
    assert membro_sync.cpf == ""


@pytest.mark.django_db
def test_paridade_justificativa_limpa_sem_mudanca_status(auth_client, municipio):
    """Limpar a justificativa de uma atividade cancelada/não realizada é
    rejeitado mesmo sem o payload tocar no campo `status`."""
    atividade_web = ActivityFactory(
        municipio=municipio, status="cancelada", justificativa="Motivo original"
    )
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk), {"justificativa": ""}, format="json"
    )
    assert response.status_code == 400
    atividade_web.refresh_from_db()
    assert atividade_web.justificativa == "Motivo original"

    atividade_sync = ActivityFactory(
        municipio=municipio, status="cancelada", justificativa="Motivo original"
    )
    resultado = _sync_update_activity(auth_client, atividade_sync, {"justificativa": ""})
    assert resultado["status"] == "erro"
    assert "JUSTIFICATIVA_OBRIGATORIA" in resultado["erro"]
    atividade_sync.refresh_from_db()
    assert atividade_sync.justificativa == "Motivo original"


@pytest.mark.django_db
def test_paridade_data_fim_anterior_a_data_inicio(auth_client, municipio):
    atividade_web = ActivityFactory(municipio=municipio, status="planejado")
    data_fim_invalida = (atividade_web.data_inicio - timedelta(days=1)).isoformat()
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk), {"data_fim": data_fim_invalida}, format="json"
    )
    assert response.status_code == 400
    assert "data_fim" in response.data

    atividade_sync = ActivityFactory(municipio=municipio, status="planejado")
    data_fim_invalida_sync = (atividade_sync.data_inicio.date() - timedelta(days=1)).isoformat()
    resultado = _sync_update_activity(
        auth_client, atividade_sync, {"data_fim": data_fim_invalida_sync}
    )
    assert resultado["status"] == "erro"
    assert "DATA_FIM_INVALIDA" in resultado["erro"]


@pytest.mark.django_db
def test_paridade_membro_fora_da_upf(auth_client, municipio, projeto):
    upf_valida = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    upf_outra = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725")

    membro_web_fora = MembroFactory(upf=upf_outra, nome_completo="Fora Web", grau_parentesco="filho", cpf="")
    atividade_web = ActivityFactory(municipio=municipio, status="planejado")
    atividade_web.upfs_participantes.set([upf_valida])
    response = auth_client.patch(
        _activity_detail_url(atividade_web.pk),
        {"membros_participantes": [membro_web_fora.pk]},
        format="json",
    )
    assert response.status_code == 400
    assert "membros_participantes" in response.data

    membro_sync_fora = MembroFactory(upf=upf_outra, nome_completo="Fora Sync", grau_parentesco="filho", cpf="")
    atividade_sync = ActivityFactory(municipio=municipio, status="planejado")
    atividade_sync.upfs_participantes.set([upf_valida])
    resultado = _sync_update_activity(
        auth_client, atividade_sync, {"membros_participantes": [membro_sync_fora.pk]}
    )
    assert resultado["status"] == "erro"
    assert "MEMBRO_FORA_UPF" in resultado["erro"]


@pytest.mark.django_db
def test_conflito_por_violacao_de_constraint_concorrente(auth_client, municipio, projeto):
    """Simula a corrida descrita na revisão: duas requisições passam juntas
    pela checagem em memória (aqui, a checagem é mockada para não pegar) e só
    a constraint do banco barra a segunda — precisa virar TITULAR_DUPLICADO
    com conflict_log, não ERRO_INTERNO genérico."""
    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")

    with patch("apps.sca.sync_entities.validar_titular_unico"):
        item = build_item(
            "member",
            operacao="create",
            payload={
                "upf": upf.pk,
                "nome_completo": "Titular Concorrente",
                "grau_parentesco": "titular",
                "cpf": "04227503523",
            },
        )
        resultado = post_batch(auth_client, [item]).data["resultados"][0]

    assert resultado["status"] == "erro"
    assert "TITULAR_DUPLICADO" in resultado["erro"]
    assert MembroFamilia.objects.filter(upf=upf, grau_parentesco="titular").count() == 1

    conflito = ConflictLog.objects.filter(
        entidade="member", estrategia=ConflictLog.Estrategia.REGRA_NEGOCIO_REJEITADA
    ).latest("id")
    assert conflito.status == ConflictLog.Status.PENDENTE
    assert conflito.campo == "grau_parentesco"


# ---------------------------------------------------------------------------
# Cenários da 2ª rodada de revisão do PR #304
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_paridade_cpf_formatado_no_create_member(auth_client, municipio, projeto):
    """CPF mascarado num CREATE (não só update) precisa ser normalizado por
    `get_by_natural` — senão a Estratégia 1 não acha o duplicata pelo texto
    bruto e o item segue adiante até cair (ainda corretamente, mas pela
    estratégia errada) na checagem de regra de negócio."""
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )
    cpf_formatado = "862.883.667-57"

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    item = build_item(
        "member",
        operacao="create",
        payload={
            "upf": upf_sync.pk,
            "nome_completo": "Novo Membro",
            "grau_parentesco": "filho",
            "cpf": cpf_formatado,
        },
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "DUPLICATA" in resultado["erro"]
    assert MembroFamilia.objects.filter(cpf=cpf_ja_usado).count() == 1

    conflito = ConflictLog.objects.filter(
        entidade="member", estrategia=ConflictLog.Estrategia.DUPLICATE_REJEITADO
    ).latest("id")
    assert conflito.status == ConflictLog.Status.RESOLVIDO_AUTO


@pytest.mark.django_db
def test_paridade_cpf_formatado_no_create_titular_upf(auth_client, municipio, projeto):
    """Mesmo cenário do teste acima, mas pelo titular de uma UPF nova."""
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )
    cpf_formatado = "862.883.667-57"

    payload = payload_upf(
        projeto, municipio, titular={"nome_completo": "Nova Titular", "cpf": cpf_formatado}
    )
    item = build_item("upf", operacao="create", payload=payload)
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "DUPLICATA" in resultado["erro"]
    assert MembroFamilia.objects.filter(cpf=cpf_ja_usado).count() == 1

    conflito = ConflictLog.objects.filter(
        entidade="upf", estrategia=ConflictLog.Estrategia.DUPLICATE_REJEITADO
    ).latest("id")
    assert conflito.status == ConflictLog.Status.RESOLVIDO_AUTO


@pytest.mark.django_db
def test_paridade_data_nascimento_futura(auth_client, municipio, projeto):
    data_futura = (date.today() + timedelta(days=30)).isoformat()

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk),
        {"data_nascimento": data_futura},
        format="json",
    )
    assert response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    item = build_item(
        "member",
        operacao="create",
        payload={
            "upf": upf_sync.pk,
            "nome_completo": "Novo Membro Nascimento",
            "grau_parentesco": "filho",
            "data_nascimento": data_futura,
        },
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "DATA_NASCIMENTO_INVALIDA" in resultado["erro"]
    assert not MembroFamilia.objects.filter(nome_completo="Novo Membro Nascimento").exists()


@pytest.mark.django_db
def test_paridade_saude_invalida(auth_client, municipio, projeto):
    saude_invalida = ["valor_inexistente"]

    upf_web = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="33355588800")
    membro_web = MembroFactory(upf=upf_web, nome_completo="Alvo Web", grau_parentesco="filho", cpf="")
    response = auth_client.patch(
        _membro_detail_url(upf_web.pk, membro_web.pk), {"saude": saude_invalida}, format="json"
    )
    assert response.status_code == 400

    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")
    item = build_item(
        "member",
        operacao="create",
        payload={
            "upf": upf_sync.pk,
            "nome_completo": "Novo Membro Saude",
            "grau_parentesco": "filho",
            "saude": saude_invalida,
        },
    )
    resultado = post_batch(auth_client, [item]).data["resultados"][0]
    assert resultado["status"] == "erro"
    assert "SAUDE_INVALIDA" in resultado["erro"]
    assert not MembroFamilia.objects.filter(nome_completo="Novo Membro Saude").exists()


@pytest.mark.django_db
def test_sync_update_atividade_participantes_validos_nao_quebra(auth_client, municipio, projeto):
    """Regressão: update de atividade com upfs_participantes/
    membros_participantes válidos não pode derrubar o item com TypeError
    (setattr direto num campo M2M) — tem que gravar com `.set()` e responder
    'ok', não estourar o lote inteiro em 500."""
    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    membro = MembroFactory(
        upf=upf, nome_completo="Participante Valido", grau_parentesco="filho", cpf=""
    )
    atividade = ActivityFactory(municipio=municipio, status="planejado")

    resultado = _sync_update_activity(
        auth_client,
        atividade,
        {"upfs_participantes": [upf.pk], "membros_participantes": [membro.pk]},
    )
    assert resultado["status"] == "ok"
    atividade.refresh_from_db()
    assert list(atividade.upfs_participantes.values_list("pk", flat=True)) == [upf.pk]
    assert list(atividade.membros_participantes.values_list("pk", flat=True)) == [membro.pk]


@pytest.mark.django_db
def test_conflito_por_violacao_de_constraint_concorrente_cpf(auth_client, municipio, projeto):
    """Mesmo padrão do teste já existente para `unique_titular_por_upf`, mas
    simulando a corrida em `unique_cpf_global`: tanto a busca por
    identificador natural (Estratégia 1) quanto a checagem em memória são
    mockadas pra "não ver" o duplicata (como aconteceria se duas requisições
    concorrentes lessem o banco antes de qualquer uma commitar) — só a
    constraint do banco barra, e precisa virar CPF_DUPLICADO com
    conflict_log, não ERRO_INTERNO genérico."""
    cpf_ja_usado = "86288366757"
    MembroFactory(
        upf=UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725"),
        nome_completo="Já Cadastrado",
        grau_parentesco="filho",
        cpf=cpf_ja_usado,
    )
    upf_sync = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="04227503523")

    def _passthrough_cpf(cpf, **kwargs):
        return normalizar_cpf(cpf)

    with patch(
        "apps.sca.sync_entities.MemberSyncEntity.get_by_natural", return_value=None
    ), patch("apps.sca.sync_entities.validar_cpf", side_effect=_passthrough_cpf):
        item = build_item(
            "member",
            operacao="create",
            payload={
                "upf": upf_sync.pk,
                "nome_completo": "Concorrente",
                "grau_parentesco": "filho",
                "cpf": cpf_ja_usado,
            },
        )
        resultado = post_batch(auth_client, [item]).data["resultados"][0]

    assert resultado["status"] == "erro"
    assert "CPF_DUPLICADO" in resultado["erro"]
    assert MembroFamilia.objects.filter(cpf=cpf_ja_usado).count() == 1

    conflito = ConflictLog.objects.filter(
        entidade="member", estrategia=ConflictLog.Estrategia.REGRA_NEGOCIO_REJEITADA
    ).latest("id")
    assert conflito.status == ConflictLog.Status.PENDENTE
    assert conflito.campo == "cpf"


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
