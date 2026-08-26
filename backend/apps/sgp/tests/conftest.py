import pytest
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgp.tests.factories import MembroFactory, ProjetoFactory, UPFFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def state_rn(db):
    return StateFactory(sigla="RN", nome="Rio Grande do Norte")


@pytest.fixture
def state_ce(db):
    return StateFactory(sigla="CE", nome="Ceará")


@pytest.fixture
def territory(db):
    return TerritoryFactory(nome="Território Teste", estados=["RN"])


@pytest.fixture
def territory_rn(db):
    return TerritoryFactory(nome="Território RN", estados=["RN"])


@pytest.fixture
def territory_ce(db):
    return TerritoryFactory(nome="Território CE", estados=["CE"])


@pytest.fixture
def municipio(db, state_rn, territory):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Mossoró",
        state=state_rn,
        territory=territory,
        codigo_ibge="2408003",
    )


@pytest.fixture
def municipio_rn(db, state_rn, territory_rn):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Mossoró",
        state=state_rn,
        territory=territory_rn,
        codigo_ibge="2408003",
    )


@pytest.fixture
def municipio_ce(db, state_ce, territory_ce):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Fortaleza",
        state=state_ce,
        territory=territory_ce,
        codigo_ibge="2304400",
    )


@pytest.fixture
def municipio_sem_territorio(db, state_rn):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Município Sem Território",
        state=state_rn,
        territory=None,
        codigo_ibge="2400001",
    )


@pytest.fixture
def outro_municipio(db, state_rn, outro_territorio):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Apodi",
        state=state_rn,
        territory=outro_territorio,
        codigo_ibge="2401104",
    )


@pytest.fixture
def outro_territorio(db):
    return TerritoryFactory(
        nome="Outro Território", estados=["RN"]
    )


@pytest.fixture
def projeto(db):
    return ProjetoFactory(nome="Projeto Teste")


@pytest.fixture
def outro_projeto(db):
    return ProjetoFactory(nome="Outro Projeto")


@pytest.fixture
def upf(db, municipio_rn, projeto):
    return UPFFactory(
        municipio=municipio_rn,
        projeto=projeto,
        ativa=True,
    )


@pytest.fixture
def upf_inativa(db, municipio_rn, projeto):
    return UPFFactory(
        municipio=municipio_rn,
        projeto=projeto,
        ativa=False,
    )


@pytest.fixture
def outra_upf(db, municipio, projeto):
    return UPFFactory(
        municipio=municipio,
        projeto=projeto,
        titular_cpf="52998224725",
        ativa=True,
    )


@pytest.fixture
def upf_ce(db, municipio_ce, projeto):
    return UPFFactory(
        municipio=municipio_ce,
        projeto=projeto,
        ativa=True,
    )


@pytest.fixture
def usuario(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(
        email="user@test.com",
        nome="Usuário Teste",
        profiles=[(role, None)],
    )


@pytest.fixture
def usuario_super_admin(db):
    role = RoleFactory(slug="super-admin", nome="Super Admin")
    return UserFactory(
        email="super@test.com",
        nome="Super Admin",
        profiles=[(role, None)],
    )


@pytest.fixture
def usuario_articulador_rn(db, territory_rn):
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    return UserFactory(
        email="articulador@test.com",
        nome="Articulador RN",
        profiles=[(role, territory_rn)],
    )


@pytest.fixture
def usuario_adt_rn(db, territory_rn):
    role = RoleFactory(slug="adt-acr", nome="ADT")
    return UserFactory(
        email="adt@test.com",
        nome="ADT RN",
        profiles=[(role, territory_rn)],
    )


@pytest.fixture
def usuario_sem_acesso(db):
    role = RoleFactory(slug="agricultor", nome="Agricultor")
    return UserFactory(
        email="agricultor@test.com",
        nome="Agricultor",
        profiles=[(role, None)],
    )


@pytest.fixture
def auth_client(api_client, usuario):
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.fixture
def auth_client_super_admin(api_client, usuario_super_admin):
    api_client.force_authenticate(user=usuario_super_admin)
    return api_client


@pytest.fixture
def auth_client_articulador_rn(api_client, usuario_articulador_rn):
    api_client.force_authenticate(user=usuario_articulador_rn)
    return api_client


@pytest.fixture
def auth_client_adt_rn(api_client, usuario_adt_rn):
    api_client.force_authenticate(user=usuario_adt_rn)
    return api_client


@pytest.fixture
def auth_client_sem_acesso(api_client, usuario_sem_acesso):
    api_client.force_authenticate(user=usuario_sem_acesso)
    return api_client


@pytest.fixture
def upf_payload_minimo(projeto, municipio):
    return {
        "projeto": projeto.pk,
        "nome": "Maria da Silva",
        "cpf": "86288366757",
        "municipio": municipio.pk,
    }


@pytest.fixture
def upf_payload_completo(projeto, municipio):
    return {
        "projeto": projeto.pk,
        "nome": "João Oliveira",
        "cpf": "52998224725",
        "rg": "1234567",
        "data_nasc": "1985-03-15",
        "genero": 1,
        "escolaridade": 7,
        "nis": "12345678901",
        "celular": "84999990002",
        "cep": "59600000",
        "logradouro": "Rua Principal",
        "numero": "100",
        "complemento": "Casa",
        "bairro": "Centro",
        "municipio": municipio.pk,
        "latitude": "-5.123456",
        "longitude": "-37.123456",
        "situacao_moradia": 1,
        "tipo_moradia": 1,
        "daf_caf": "DAP123456",
        "foto_url": "https://example.com/foto.jpg",
    }


@pytest.fixture
def membro_payload_minimo(upf):
    return {
        "nome": "João Filho",
        "parentesco": "filho",
    }


@pytest.fixture
def titular_payload(upf):
    return {
        "nome": "Maria Titular",
        "parentesco": "titular",
        "data_nasc": "1980-05-10",
    }


@pytest.fixture
def membro(upf):
    return MembroFactory(
        upf=upf,
        nome_completo="Membro Existente",
        parentesco="filho",
    )


@pytest.fixture
def membro_outra_upf(outra_upf):
    return MembroFactory(
        upf=outra_upf,
        nome_completo="Membro de Outra UPF",
        parentesco="filho",
    )


# ---------------------------------------------------------------------------
# Comunidade fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def super_admin_client(api_client):
    role = RoleFactory(slug='super-admin', nome='Super Admin')
    user = UserFactory(profiles=[(role, None)])
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def ugp_client(api_client):
    role = RoleFactory(slug='ugp', nome='UGP')
    user = UserFactory(profiles=[(role, None)])
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def adt_client(api_client):
    role = RoleFactory(slug='adt-acr', nome='ADT / ACR')
    user = UserFactory(profiles=[(role, None)])
    api_client.force_authenticate(user=user)
    return api_client
