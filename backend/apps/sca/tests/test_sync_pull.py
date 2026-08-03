"""
Testes do endpoint GET /api/v1/sca/sync/pull.

Delta sync por `since`, full sync na primeira chamada, soft-delete com
`ativo=false` e isolamento territorial.
"""

import time
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.sca.models import SyncDevice, SyncEvent
from apps.sgp.models import Activity, MembroFamilia, UPF
from apps.sgp.tests.factories import MembroFactory, UPFFactory


def get_pull(auth_client, device_id="dev-001", since=None):
    params = {}
    if since is not None:
        params["since"] = since.isoformat()
    return auth_client.get(
        "/api/v1/sca/sync/pull/",
        data=params,
        HTTP_X_DEVICE_ID=device_id,
        format="json",
    )


def _set_updated_at(queryset, dt):
    queryset.update(atualizado_em=dt)


# ---------------------------------------------------------------------------
# Pull com since → apenas registros modificados depois do timestamp
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_com_since_retorna_apenas_alterados(auth_client, usuario, municipio, projeto):
    antiga = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="11144477735")
    recente = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725")

    _set_updated_at(UPF.objects.filter(pk=antiga.pk), timezone.now() - timedelta(hours=3))
    _set_updated_at(UPF.objects.filter(pk=recente.pk), timezone.now() - timedelta(minutes=30))

    since = timezone.now() - timedelta(hours=1)
    response = get_pull(auth_client, since=since)

    assert response.status_code == 200
    ids = [r["id"] for r in response.data["upfs"]]
    assert recente.pk in ids
    assert antiga.pk not in ids
    assert response.data["server_time"]


# ---------------------------------------------------------------------------
# Pull sem since → full sync da carteira do técnico
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_sem_since_retorna_conjunto_completo(auth_client, usuario, municipio, projeto):
    a = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="11144477735")
    b = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="52998224725")
    _set_updated_at(UPF.objects.filter(pk__in=[a.pk, b.pk]), timezone.now() - timedelta(days=10))

    response = get_pull(auth_client)

    assert response.status_code == 200
    ids = {r["id"] for r in response.data["upfs"]}
    assert ids == {a.pk, b.pk}
    assert len(response.data["members"]) == 2  # titulares (MembroFamilia) também sincronizam
    assert response.data["activities"] == []


# ---------------------------------------------------------------------------
# Soft-delete → incluído com ativo=false
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_soft_delete_vem_com_ativo_false(auth_client, usuario, municipio, projeto):
    inativa = UPFFactory(municipio=municipio, projeto=projeto, ativa=False, titular_cpf="11144477735")
    _set_updated_at(UPF.objects.filter(pk=inativa.pk), timezone.now() - timedelta(minutes=5))

    response = get_pull(auth_client, since=timezone.now() - timedelta(days=1))

    assert response.status_code == 200
    encontrada = [r for r in response.data["upfs"] if r["id"] == inativa.pk]
    assert encontrada, "UPF inativa deveria aparecer no delta"
    assert encontrada[0]["ativo"] is False


# ---------------------------------------------------------------------------
# Membros e atividades também sincronizam (delta)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_inclui_membros_e_atividades(auth_client, usuario, municipio, projeto, upf, acao):
    membro = MembroFactory(upf=upf, cpf="12345678901")
    atividade = Activity.objects.create(
        titulo="Visita técnica",
        tipo_atividade="visita_tecnica",
        acao=acao,
        forma_atuacao="realizacao",
        municipio=municipio,
        tecnico_responsavel=usuario,
        ambito="municipal",
        data_inicio="2026-08-01",
        data_fim="2026-08-01",
        descricao_narrativa="Descrição",
    )
    _set_updated_at(MembroFamilia.objects.filter(pk=membro.pk), timezone.now() - timedelta(minutes=5))
    _set_updated_at(Activity.objects.filter(pk=atividade.pk), timezone.now() - timedelta(minutes=5))

    response = get_pull(auth_client, since=timezone.now() - timedelta(hours=1))

    assert response.status_code == 200
    member_ids = [r["id"] for r in response.data["members"]]
    activity_ids = [r["id"] for r in response.data["activities"]]
    assert membro.pk in member_ids
    assert atividade.pk in activity_ids


# ---------------------------------------------------------------------------
# Isolamento territorial — técnico A não recebe registros de B
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_isolamento_territorial(auth_client, usuario, municipio, municipio_outro, projeto):
    UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="11144477735")
    fora = UPFFactory(municipio=municipio_outro, projeto=projeto, titular_cpf="52998224725")

    response = get_pull(auth_client)

    assert response.status_code == 200
    ids = {r["id"] for r in response.data["upfs"]}
    assert fora.pk not in ids
    assert len(ids) == 1


# ---------------------------------------------------------------------------
# Pull registra device + evento (ultimo_pull_em)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_registra_device_e_evento(auth_client, usuario, municipio, projeto):
    get_pull(auth_client)

    device = SyncDevice.objects.get(user=usuario, device_id="dev-001")
    assert device.ultimo_pull_em is not None
    assert SyncEvent.objects.filter(user=usuario, tipo=SyncEvent.Tipo.PULL).count() == 1


# ---------------------------------------------------------------------------
# Performance: 500 registros dentro do limite (< 3s)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_pull_performance_500_registros(auth_client, usuario, municipio, projeto):
    for i in range(500):
        UPFFactory(
            municipio=municipio,
            projeto=projeto,
            titular_cpf=f"{i:011d}",
        )

    inicio = time.perf_counter()
    response = get_pull(auth_client)
    duracao = time.perf_counter() - inicio

    assert response.status_code == 200
    assert len(response.data["upfs"]) == 500
    assert duracao < 3.0, f"Pull demorou {duracao:.2f}s (limite: 3s)"


@pytest.fixture
def upf(db, municipio, projeto):
    return UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")


@pytest.fixture
def acao(db):
    from apps.sgp.tests.factories import WorkPlanAcaoFactory

    return WorkPlanAcaoFactory()
