import pytest
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    MunicipalityFactory,
    RoleFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory
from apps.sgp.tests.factories import ActivityFactory, BudgetAllocationFactory, BudgetRubricaFactory, WorkPlanAcaoFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def territory_rn(db):
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def territory_ce(db):
    return TerritoryFactory(nome="Território CE", estados=["CE"])


@pytest.fixture
def municipio_rn(db, territory_rn):
    from apps.core.tests.factories import StateFactory
    return MunicipalityFactory(
        nome="Mossoró", state=StateFactory(sigla="RN", nome="Rio Grande do Norte"),
        territory=territory_rn, codigo_ibge="2408003",
    )


@pytest.fixture
def municipio_ce(db, territory_ce):
    from apps.core.tests.factories import StateFactory
    return MunicipalityFactory(
        nome="Fortaleza", state=StateFactory(sigla="CE", nome="Ceará"),
        territory=territory_ce, codigo_ibge="2304400",
    )


@pytest.fixture
def rubrica_diarias(db):
    return BudgetRubricaFactory(slug="diarias", nome="Diárias")


@pytest.fixture
def solicitante_rn(db, territory_rn):
    role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
    return UserFactory(email="adt.rn@test.com", nome="ADT RN", profiles=[(role, territory_rn)])


@pytest.fixture
def activity_rn(db, municipio_rn, solicitante_rn):
    return ActivityFactory(
        municipio=municipio_rn, tecnico_responsavel=solicitante_rn, status="planejado",
        acao=WorkPlanAcaoFactory(),
    )


@pytest.fixture
def allocation_territorial_rn(db, activity_rn, rubrica_diarias):
    return BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )


@pytest.fixture
def limite_individual_rn(db, solicitante_rn, rubrica_diarias):
    return DemandIndividualLimitFactory(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor_limite=5_000,
    )


@pytest.fixture
def demand_rascunho_rn(db, activity_rn, solicitante_rn):
    return DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="rascunho")


@pytest.fixture
def demand_request_rn(db, demand_rascunho_rn, rubrica_diarias):
    return DemandRequestFactory(
        demanda=demand_rascunho_rn, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=1_000,
    )


@pytest.fixture
def usuario_articulador_rn(db, territory_rn):
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    return UserFactory(email="articulador.rn@test.com", nome="Articulador RN", profiles=[(role, territory_rn)])


@pytest.fixture
def usuario_articulador_ce(db, territory_ce):
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    return UserFactory(email="articulador.ce@test.com", nome="Articulador CE", profiles=[(role, territory_ce)])


@pytest.fixture
def usuario_ugp(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(email="ugp@test.com", nome="UGP", profiles=[(role, None)])


@pytest.fixture
def usuario_fgd(db):
    role = RoleFactory(slug="fgd", nome="FGD")
    return UserFactory(email="fgd@test.com", nome="FGD", profiles=[(role, None)])


@pytest.fixture
def usuario_super_admin(db):
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    return UserFactory(email="super@test.com", nome="Super Admin", profiles=[(role, None)])


@pytest.fixture
def auth_client_solicitante(api_client, solicitante_rn):
    api_client.force_authenticate(user=solicitante_rn)
    return api_client


@pytest.fixture
def auth_client_articulador_rn(api_client, usuario_articulador_rn):
    api_client.force_authenticate(user=usuario_articulador_rn)
    return api_client


@pytest.fixture
def auth_client_articulador_ce(api_client, usuario_articulador_ce):
    api_client.force_authenticate(user=usuario_articulador_ce)
    return api_client


@pytest.fixture
def auth_client_ugp(api_client, usuario_ugp):
    api_client.force_authenticate(user=usuario_ugp)
    return api_client


@pytest.fixture
def auth_client_fgd(api_client, usuario_fgd):
    api_client.force_authenticate(user=usuario_fgd)
    return api_client


@pytest.fixture
def auth_client_super_admin(api_client, usuario_super_admin):
    api_client.force_authenticate(user=usuario_super_admin)
    return api_client
