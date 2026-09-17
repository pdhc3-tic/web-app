"""
Testes de GET /api/v1/sca/tecnicos/ — fonte completa de técnicos para o
filtro por técnico de /sca/sync-events/ (#157, item 7 do backlog).
"""

import pytest

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sca.tests.factories import SyncDeviceFactory, SyncEventFactory


pytestmark = pytest.mark.django_db

TECNICOS_URL = "/api/v1/sca/tecnicos/"


@pytest.fixture
def ugp_user(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="Usuário UGP", profiles=[(role, None)])


@pytest.fixture
def auth_client_ugp(api_client, ugp_user):
    api_client.force_authenticate(user=ugp_user)
    return api_client


# --- permissão (mesma restrição de SyncDeviceListView/SyncEventViewSet) ----

def test_anonymous_gets_401(api_client):
    response = api_client.get(TECNICOS_URL)

    assert response.status_code == 401


def test_adt_is_forbidden(auth_client):
    response = auth_client.get(TECNICOS_URL)

    assert response.status_code == 403


def test_articulador_is_forbidden(api_client, articulador):
    api_client.force_authenticate(user=articulador)
    response = api_client.get(TECNICOS_URL)

    assert response.status_code == 403


def test_ugp_can_list(auth_client_ugp):
    response = auth_client_ugp.get(TECNICOS_URL)

    assert response.status_code == 200


def test_super_admin_can_list(auth_client_super_admin):
    response = auth_client_super_admin.get(TECNICOS_URL)

    assert response.status_code == 200


# --- conteúdo ----------------------------------------------------------------

def test_technician_with_only_a_device_is_included(auth_client_super_admin):
    device = SyncDeviceFactory()

    response = auth_client_super_admin.get(TECNICOS_URL)

    assert response.status_code == 200
    ids = [item["id"] for item in response.data]
    assert device.user_id in ids


def test_technician_with_only_an_event_is_included(auth_client_super_admin):
    """O buraco que a issue corrige: um técnico sem dispositivo (só evento)
    tinha que aparecer no filtro, mas ficava de fora de quem derivava as
    opções só da listagem de dispositivos."""
    tecnico = UserFactory(nome="Técnico Só Evento")
    SyncEventFactory(user=tecnico, device=SyncDeviceFactory())

    response = auth_client_super_admin.get(TECNICOS_URL)

    ids = [item["id"] for item in response.data]
    assert tecnico.pk in ids


def test_technician_without_device_or_event_is_excluded(auth_client_super_admin):
    sem_atividade = UserFactory(nome="Sem Sync")

    response = auth_client_super_admin.get(TECNICOS_URL)

    ids = [item["id"] for item in response.data]
    assert sem_atividade.pk not in ids


def test_technician_with_multiple_devices_appears_once(auth_client_super_admin):
    tecnico = UserFactory(nome="Multi Dispositivo")
    SyncDeviceFactory(user=tecnico, device_id="dev-a")
    SyncDeviceFactory(user=tecnico, device_id="dev-b")
    SyncDeviceFactory(user=tecnico, device_id="dev-c")

    response = auth_client_super_admin.get(TECNICOS_URL)

    ids = [item["id"] for item in response.data]
    assert ids.count(tecnico.pk) == 1


def test_technician_with_multiple_events_appears_once(auth_client_super_admin):
    tecnico = UserFactory(nome="Multi Evento")
    device = SyncDeviceFactory(user=tecnico)
    SyncEventFactory(user=tecnico, device=device)
    SyncEventFactory(user=tecnico, device=device)

    response = auth_client_super_admin.get(TECNICOS_URL)

    ids = [item["id"] for item in response.data]
    assert ids.count(tecnico.pk) == 1


def test_technician_with_revoked_access_still_included(auth_client_super_admin):
    """Decisão deliberada: o filtro é sobre histórico de sincronização já
    existente, não sobre quem está ativo hoje — excluir revogados quebraria
    a possibilidade de filtrar eventos antigos desse técnico."""
    revogado = UserFactory(nome="Ex-Técnico", acesso_revogado=True)
    SyncDeviceFactory(user=revogado)

    response = auth_client_super_admin.get(TECNICOS_URL)

    ids = [item["id"] for item in response.data]
    assert revogado.pk in ids


def test_response_shape_has_id_nome_email(auth_client_super_admin):
    device = SyncDeviceFactory()

    response = auth_client_super_admin.get(TECNICOS_URL)

    item = next(i for i in response.data if i["id"] == device.user_id)
    assert item == {
        "id": device.user_id,
        "nome": device.user.nome,
        "email": device.user.email,
    }


def test_response_is_not_paginated(auth_client_super_admin):
    SyncDeviceFactory()

    response = auth_client_super_admin.get(TECNICOS_URL)

    assert isinstance(response.data, list)


def test_ordering_is_stable_by_name(auth_client_super_admin):
    zeta = UserFactory(nome="Zeta Técnico")
    alfa = UserFactory(nome="Alfa Técnico")
    SyncDeviceFactory(user=zeta)
    SyncDeviceFactory(user=alfa)

    response = auth_client_super_admin.get(TECNICOS_URL)

    nomes = [item["nome"] for item in response.data]
    assert nomes.index("Alfa Técnico") < nomes.index("Zeta Técnico")
