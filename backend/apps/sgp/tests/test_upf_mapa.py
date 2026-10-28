import json
from datetime import datetime

import pytest
from django.core.cache import cache
from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory
from apps.sgp.cache import build_upf_map_cache_key
from apps.sgp.filters import UPFFilter
from apps.sgp.models import UPF
from apps.sgp.tests.factories import ComunidadeFactory, UPFFactory
from apps.sgp.views import UPFViewSet


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_upf(
    projeto,
    municipio,
    territory,
    cpf,
    nome="João Silva",
    latitude="-5.160000",
    longitude="-37.840000",
    ativo=True,
):
    return UPFFactory(
        projeto=projeto,
        municipio=municipio,
        territorio=territory,
        _titular_nome=nome,
        titular_cpf=cpf,
        latitude=latitude,
        longitude=longitude,
        ativo=ativo,
    )


def feature_ids(response):
    return [feature["properties"]["id"] for feature in response.data["features"]]


def test_mapa_returns_geojson_format(auth_client, projeto, municipio_rn, territory_rn):
    upf = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        nome="João Silva",
    )

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    assert response.data["truncated"] is False
    assert len(response.data["features"]) == 1

    feature = response.data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {
        "type": "Point",
        "coordinates": [-37.84, -5.16],
    }
    assert feature["properties"] == {
        "id": upf.pk,
        "nome_titular": "João Silva",
        "municipio": {
            "id": municipio_rn.pk,
            "nome": municipio_rn.nome,
            "estado": {
                "id": municipio_rn.state_id,
                "sigla": municipio_rn.state.sigla,
                "nome": municipio_rn.state.nome,
            },
        },
        "territorio": territory_rn.nome,
        "ativo": True,
    }


def test_mapa_excludes_upfs_without_coordinates(auth_client, projeto, municipio_rn, territory_rn):
    visible = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
    )
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        latitude=None,
        longitude="-37.840000",
    )

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert feature_ids(response) == [visible.pk]


def test_mapa_excludes_inactive_upfs_by_default(auth_client, projeto, municipio_rn, territory_rn):
    active = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        ativo=True,
    )
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        ativo=False,
    )

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert feature_ids(response) == [active.pk]


def test_mapa_filter_by_ativo_false(auth_client, projeto, municipio_rn, territory_rn):
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        ativo=True,
    )
    inactive = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        ativo=False,
    )

    response = auth_client.get("/api/v1/upfs/mapa/?ativo=false")

    assert response.status_code == 200
    assert feature_ids(response) == [inactive.pk]


def test_mapa_filter_by_bbox(auth_client, projeto, municipio_rn, territory_rn):
    inside = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        latitude="-5.500000",
        longitude="-37.500000",
    )
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        latitude="-4.000000",
        longitude="-37.500000",
    )

    response = auth_client.get("/api/v1/upfs/mapa/?bbox=-38,-6,-37,-5")

    assert response.status_code == 200
    assert feature_ids(response) == [inside.pk]


def test_mapa_filter_by_municipio_and_bbox_combined(
    auth_client,
    projeto,
    municipio_rn,
    municipio_ce,
    territory_rn,
    territory_ce,
):
    expected = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        latitude="-5.500000",
        longitude="-37.500000",
    )
    make_upf(
        projeto,
        municipio_ce,
        territory_ce,
        cpf="52998224725",
        latitude="-5.500000",
        longitude="-37.500000",
    )

    response = auth_client.get(
        f"/api/v1/upfs/mapa/?municipio={municipio_rn.pk}&bbox=-38,-6,-37,-5"
    )

    assert response.status_code == 200
    assert feature_ids(response) == [expected.pk]


def test_mapa_adt_sees_only_own_territory(
    auth_client_adt_rn,
    projeto,
    municipio_rn,
    municipio_ce,
    territory_rn,
    territory_ce,
):
    upf_rn = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
    )
    make_upf(
        projeto,
        municipio_ce,
        territory_ce,
        cpf="52998224725",
    )

    response = auth_client_adt_rn.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert feature_ids(response) == [upf_rn.pk]


def test_mapa_truncates_at_10000_features(
    auth_client,
    projeto,
    municipio_rn,
    territory_rn,
    monkeypatch,
):
    monkeypatch.setattr(UPFViewSet, "MAPA_FEATURE_LIMIT", 2)
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")
    make_upf(projeto, municipio_rn, territory_rn, cpf="52998224725")
    make_upf(projeto, municipio_rn, territory_rn, cpf="15350946056")

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert len(response.data["features"]) == 2
    assert response.data["truncated"] is True
    assert "Use o filtro bbox" in response.data["message"]


def test_mapa_query_uses_only_required_fields(
    auth_client_super_admin,
    projeto,
    municipio_rn,
    territory_rn,
):
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    with CaptureQueriesContext(connection) as ctx:
        response = auth_client_super_admin.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert len(ctx.captured_queries) <= 3


def test_mapa_cache_hit_on_repeated_request(
    auth_client,
    projeto,
    municipio_rn,
    territory_rn,
    django_assert_num_queries,
):
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    first = auth_client.get("/api/v1/upfs/mapa/")
    assert first.status_code == 200

    with django_assert_num_queries(0):
        second = auth_client.get("/api/v1/upfs/mapa/")

    assert second.status_code == 200
    assert second.data == first.data


def test_mapa_cache_invalidated_on_upf_save(
    auth_client,
    projeto,
    municipio_rn,
    territory_rn,
):
    first_upf = make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")
    first = auth_client.get("/api/v1/upfs/mapa/")
    assert feature_ids(first) == [first_upf.pk]

    new_upf = make_upf(projeto, municipio_rn, territory_rn, cpf="52998224725")
    second = auth_client.get("/api/v1/upfs/mapa/")

    assert second.status_code == 200
    assert feature_ids(second) == [first_upf.pk, new_upf.pk]


def test_mapa_busca_sem_resultado_nao_reaproveita_o_cache_sem_filtro(
    auth_client, projeto, municipio_rn, territory_rn,
):
    upf = make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    sem_filtro = auth_client.get("/api/v1/upfs/mapa/")
    com_busca = auth_client.get("/api/v1/upfs/mapa/?q=texto-que-nao-existe")

    assert feature_ids(sem_filtro) == [upf.pk]
    assert com_busca.status_code == 200
    assert feature_ids(com_busca) == []


def test_mapa_sem_filtro_nao_reaproveita_o_cache_da_busca(
    auth_client, projeto, municipio_rn, territory_rn,
):
    upf = make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    com_busca = auth_client.get("/api/v1/upfs/mapa/?q=texto-que-nao-existe")
    sem_filtro = auth_client.get("/api/v1/upfs/mapa/")

    assert feature_ids(com_busca) == []
    assert feature_ids(sem_filtro) == [upf.pk]


@pytest.mark.parametrize(
    ("montar_params", "esperada"),
    [
        (lambda comunidade: "q=Maria", "a"),
        (lambda comunidade: f"comunidade={comunidade.pk}", "a"),
        (lambda comunidade: "cadastrado_de=2025-01-01", "a"),
        (lambda comunidade: "cadastrado_ate=2020-12-31", "b"),
    ],
    ids=["q", "comunidade", "cadastrado_de", "cadastrado_ate"],
)
def test_mapa_com_filtro_depois_do_mapa_sem_filtro_respeita_o_filtro(
    auth_client, projeto, municipio_rn, territory_rn, montar_params, esperada,
):
    comunidade = ComunidadeFactory(municipio=municipio_rn)
    upfs = {
        "a": make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757", nome="Maria Souza"),
        "b": make_upf(projeto, municipio_rn, territory_rn, cpf="52998224725", nome="José Lima"),
    }
    UPF.all_objects.filter(pk=upfs["a"].pk).update(comunidade=comunidade)
    UPF.all_objects.filter(pk=upfs["b"].pk).update(
        criado_em=timezone.make_aware(datetime(2020, 6, 1, 12, 0)),
    )

    sem_filtro = auth_client.get("/api/v1/upfs/mapa/")
    filtrado = auth_client.get(f"/api/v1/upfs/mapa/?{montar_params(comunidade)}")

    assert sorted(feature_ids(sem_filtro)) == sorted(upf.pk for upf in upfs.values())
    assert filtrado.status_code == 200
    assert feature_ids(filtrado) == [upfs[esperada].pk]


@pytest.mark.parametrize("nome", ["bbox", *UPFFilter.base_filters])
def test_chave_do_cache_do_mapa_considera_todo_filtro_do_upf_filter(nome):
    sem_filtro = build_upf_map_cache_key(1, QueryDict(""))
    com_filtro = build_upf_map_cache_key(1, QueryDict(f"{nome}=1"))

    assert com_filtro != sem_filtro


def test_chave_do_cache_do_mapa_ignora_parametro_que_nao_filtra():
    sem_filtro = build_upf_map_cache_key(1, QueryDict(""))
    com_ordenacao = build_upf_map_cache_key(1, QueryDict("ordering=criado_em"))

    assert com_ordenacao == sem_filtro


def test_mapa_inclui_estado(auth_client, projeto, municipio_rn, territory_rn):
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert response.data["features"][0]["properties"]["municipio"]["estado"]["sigla"] == "RN"


def test_mapa_nao_gera_query_adicional_por_estado(
    auth_client, projeto, municipio_rn, territory_rn,
):
    for i in range(50):
        make_upf(projeto, municipio_rn, territory_rn, cpf=f"{i + 10000000000:011d}")

    with CaptureQueriesContext(connection) as ctx:
        response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert len(response.data["features"]) == 50
    assert len(ctx.captured_queries) <= 3


def test_mapa_nao_recheca_roles_do_usuario(auth_client, projeto, municipio_rn, territory_rn):
    """Regressão: get_queryset não deve refazer a checagem de roles já feita
    por upfs_acessiveis_ao_usuario (ver user_role_slugs)."""
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    with CaptureQueriesContext(connection) as ctx:
        response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert len(ctx.captured_queries) <= 2


def test_mapa_articulador_sem_estado_retorna_lista_vazia(
    api_client, projeto, municipio_rn, territory_rn,
):
    """Articulador com a role, mas cujo território não tem estado algum
    vinculado, não vê UPFs — mas continua recebendo 200, não 403."""
    make_upf(projeto, municipio_rn, territory_rn, cpf="86288366757")

    territorio_sem_estado = TerritoryFactory(nome="Território Sem Estado", estados=[])
    role = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
    usuario = UserFactory(
        email="articulador-sem-estado@test.com",
        nome="Articulador Sem Estado",
        profiles=[(role, territorio_sem_estado)],
    )
    api_client.force_authenticate(user=usuario)

    response = api_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert response.data["features"] == []


def test_mapa_openapi_schema_tipa_municipio_estado(auth_client_super_admin):
    """O @extend_schema de /mapa/ deve tipar properties.municipio.estado, e não
    documentar 'features' como uma lista de objetos genéricos (DictField)."""
    response = auth_client_super_admin.get("/api/docs/schema/", {"format": "json"})
    assert response.status_code == 200

    schema = json.loads(response.content)
    components = schema["components"]["schemas"]

    def resolve(node):
        if isinstance(node, dict) and "allOf" in node and len(node["allOf"]) == 1:
            node = node["allOf"][0]
        if isinstance(node, dict) and "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return components[name]
        return node

    mapa_get = schema["paths"]["/api/v1/upfs/mapa/"]["get"]
    response_schema = resolve(
        mapa_get["responses"]["200"]["content"]["application/json"]["schema"]
    )

    features_schema = resolve(response_schema["properties"]["features"])
    assert features_schema["type"] == "array"

    feature_item = resolve(features_schema["items"])
    assert "additionalProperties" not in feature_item, (
        "features não deve mais ser tipado como lista de objetos genéricos"
    )

    properties_schema = resolve(feature_item["properties"]["properties"])
    municipio_schema = resolve(properties_schema["properties"]["municipio"])
    estado_schema = resolve(municipio_schema["properties"]["estado"])

    assert set(estado_schema["properties"]) == {"id", "sigla", "nome"}
