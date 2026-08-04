import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.sgp.tests.factories import UPFFactory
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
    ativa=True,
):
    return UPFFactory(
        projeto=projeto,
        municipio=municipio,
        territorio=territory,
        _titular_nome=nome,
        titular_cpf=cpf,
        latitude=latitude,
        longitude=longitude,
        ativa=ativa,
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
        "municipio": municipio_rn.nome,
        "territorio": territory_rn.nome,
        "ativa": True,
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
        ativa=True,
    )
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        ativa=False,
    )

    response = auth_client.get("/api/v1/upfs/mapa/")

    assert response.status_code == 200
    assert feature_ids(response) == [active.pk]


def test_mapa_filter_by_ativa_false(auth_client, projeto, municipio_rn, territory_rn):
    make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="86288366757",
        ativa=True,
    )
    inactive = make_upf(
        projeto,
        municipio_rn,
        territory_rn,
        cpf="52998224725",
        ativa=False,
    )

    response = auth_client.get("/api/v1/upfs/mapa/?ativa=false")

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
