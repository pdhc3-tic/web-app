from datetime import datetime

import pytest
from django.utils import timezone

from apps.sgp.tests.factories import FormResponseFactory, UPFFactory


pytestmark = pytest.mark.django_db


def list_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/"


def detail_url(upf, response):
    return f"{list_url(upf)}{response.pk}/"


def response_results(response):
    return response.data["results"] if "results" in response.data else response.data


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


def test_list_returns_responses_in_reverse_chronological_order(auth_client, upf):
    oldest = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 1, 1))
    newest = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 3, 1))

    response = auth_client.get(list_url(upf))

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [newest.pk, oldest.pk]


def test_list_filters_by_formulario_id(auth_client, upf):
    expected = FormResponseFactory(upf=upf, formulario_id=12)
    FormResponseFactory(upf=upf, formulario_id=13)

    response = auth_client.get(list_url(upf), {"formulario_id": 12})

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [expected.pk]


def test_list_filters_by_completion_period(auth_client, upf):
    before = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 1, 10))
    expected = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 2, 15))
    after = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 3, 10))

    response = auth_client.get(
        list_url(upf),
        {"data_inicio": "2026-02-01", "data_fim": "2026-02-28"},
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response_results(response)]
    assert ids == [expected.pk]
    assert before.pk not in ids
    assert after.pk not in ids


def test_list_preserves_null_respondent(auth_client, upf):
    form_response = FormResponseFactory(upf=upf, respondente=None)

    response = auth_client.get(list_url(upf))

    assert response.status_code == 200
    item = next(item for item in response_results(response) if item["id"] == form_response.pk)
    assert item["respondente"] is None


def test_adt_cannot_list_responses_from_another_territory(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    FormResponseFactory(upf=upf_ce)

    response = auth_client_adt_rn.get(list_url(upf_ce))

    assert response.status_code == 404


def test_detail_returns_complete_response_json(auth_client, upf):
    respostas_json = {"secao": {"pergunta": ["sim", "não"]}}
    form_response = FormResponseFactory(upf=upf, respostas_json=respostas_json)

    response = auth_client.get(detail_url(upf, form_response))

    assert response.status_code == 200
    assert response.data["id"] == form_response.pk
    assert response.data["respostas_json"] == respostas_json


def test_detail_returns_404_when_response_belongs_to_another_upf(auth_client, upf, outra_upf):
    other_response = FormResponseFactory(upf=outra_upf)

    response = auth_client.get(detail_url(upf, other_response))

    assert response.status_code == 404


def test_adt_cannot_retrieve_response_from_another_territory(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    form_response = FormResponseFactory(upf=upf_ce)

    response = auth_client_adt_rn.get(detail_url(upf_ce, form_response))

    assert response.status_code == 404
