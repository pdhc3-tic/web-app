import pytest
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgp.tests.factories import ProjetoFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def state_rn(db):
    return StateFactory(sigla="RN", nome="Rio Grande do Norte")


@pytest.fixture
def territory(db):
    return TerritoryFactory(nome="Território Teste", estados=["RN"])


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
def municipio_sem_territorio(db, state_rn):
    from apps.core.tests.factories import MunicipalityFactory
    return MunicipalityFactory(
        nome="Município Sem Território",
        state=state_rn,
        territory=None,
        codigo_ibge="2400001",
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
def usuario(db):
    role = RoleFactory(slug="ugp", nome="UGP")
    return UserFactory(
        email="user@test.com",
        nome="Usuário Teste",
        role=role,
    )


@pytest.fixture
def auth_client(api_client, usuario):
    api_client.force_authenticate(user=usuario)
    return api_client


@pytest.fixture
def upf_payload_minimo(projeto, municipio):
    return {
        "projeto": projeto.pk,
        "nome_titular": "Maria da Silva",
        "cpf": "862.883.667-57",
        "municipio": municipio.pk,
    }


@pytest.fixture
def upf_payload_completo(projeto, municipio):
    return {
        "projeto": projeto.pk,
        "nome_titular": "João Oliveira",
        "cpf": "529.982.247-25",
        "rg": "1234567",
        "data_nascimento": "1985-03-15",
        "genero": "masculino",
        "estado_civil": "casado",
        "nacionalidade": "brasileira",
        "naturalidade": "Mossoró",
        "nome_mae": "Mãe do João",
        "nome_pai": "Pai do João",
        "telefone": "84999990001",
        "celular": "84999990002",
        "email": "joao@example.com",
        "cep": "59600000",
        "logradouro": "Rua Principal",
        "numero": "100",
        "complemento": "Casa",
        "bairro": "Centro",
        "municipio": municipio.pk,
        "latitude": "-5.123456",
        "longitude": "-37.123456",
        "situacao_moradia": "propria",
        "tipo_moradia": "casa",
        "numero_dap": "DAP123456",
        "nis": "12345678901",
        "foto_url": "https://example.com/foto.jpg",
    }
