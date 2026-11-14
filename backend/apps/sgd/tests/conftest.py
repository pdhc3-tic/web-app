from importlib import import_module

import pytest
from rest_framework.test import APIClient

from apps.core.tests.factories import (
    MunicipalityFactory,
    RoleFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgd.models import TipoSolicitacao
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory, TipoSolicitacaoFactory
from apps.sgp.tests.factories import (
    ActivityFactory,
    BudgetPoolFactory,
    BudgetRubricaFactory,
    SpendingLimitFactory,
    WorkPlanAcaoFactory,
)


@pytest.fixture(autouse=True)
def catalogo_de_tipos(request):
    """Os testes com `transaction=True` apagam o que as migrations semearam."""
    if not request.node.get_closest_marker("django_db"):
        return
    request.getfixturevalue("db")
    if TipoSolicitacao.objects.exists():
        return
    semeadura = import_module("apps.sgd.migrations.0020_tipo_solicitacao")
    for ordem, (slug, nome, rubrica, schema) in enumerate(semeadura.TIPOS, start=1):
        TipoSolicitacaoFactory(
            slug=slug, nome=nome, rubrica=BudgetRubricaFactory(slug=rubrica), schema_campos=schema,
            validador=slug, ordem=ordem,
        )


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
    return BudgetPoolFactory(
        rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )


@pytest.fixture
def limite_individual_rn(db, solicitante_rn, rubrica_diarias):
    return SpendingLimitFactory(
        user=solicitante_rn, rubrica=rubrica_diarias, valor_limite=5_000,
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


@pytest.fixture
def faixas_diaria(db):
    """As faixas semeadas pela migration; recriadas nos testes com `transaction=True`."""
    from apps.sgd.models import EnquadramentoFaixaDiaria, FaixaDestinoDiaria

    semeadura = import_module("apps.sgd.migrations.0023_seed_faixas_diarias")
    semeadura.semear_faixas(FaixaDestinoDiaria, EnquadramentoFaixaDiaria)
    return {faixa.ordem: faixa for faixa in FaixaDestinoDiaria.objects.all()}


@pytest.fixture
def regras_diaria(db):
    """`regras_diaria(sgd_diaria_regra_meia_no_retorno=False, ...)` grava os parâmetros do Core.
    O cache do SystemConfig não é transacional: limpa ao fim para não vazar."""
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    chaves = []

    def configurar(**parametros):
        for chave, valor in parametros.items():
            tipo = TipoConfiguracao.BOOLEAN if isinstance(valor, bool) else TipoConfiguracao.STRING
            SystemConfig.objects.update_or_create(chave=chave, defaults={"valor": str(valor), "tipo": tipo})
            cache.delete(f"system_config:{chave}")
            chaves.append(chave)

    yield configurar
    for chave in chaves:
        cache.delete(f"system_config:{chave}")


@pytest.fixture
def tabela_diaria(faixas_diaria):
    """`tabela_diaria("300")` cadastra o mesmo valor, desde 2000, em todas as faixas."""
    from datetime import date
    from decimal import Decimal

    from apps.sgd.models import TabelaDiaria

    def configurar(valor, *, faixas=None, inicio=date(2000, 1, 1), fim=None, origem="fgd"):
        return [
            TabelaDiaria.objects.create(
                faixa_destino=faixa, vigencia_inicio=inicio, vigencia_fim=fim, valor=Decimal(str(valor)),
                origem=origem,
            )
            for faixa in (faixas or faixas_diaria.values())
        ]

    return configurar
