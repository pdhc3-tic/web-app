from datetime import datetime

import pytest
from django.utils import timezone

from apps.sgp.models import FormResponse
from apps.sgp.tests.factories import FormResponseFactory, UFPAFactory


pytestmark = pytest.mark.django_db


def list_url(ufpa):
    return f"/api/v1/sgp/ufpas/{ufpa.pk}/formularios/"


def detail_url(ufpa, response):
    return f"{list_url(ufpa)}{response.pk}/"


RECEIVE_URL = "/api/v1/sgp/formularios/respostas/"


def response_results(response):
    return response.data["results"] if "results" in response.data else response.data


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


def receive_payload(ufpa, **overrides):
    payload = {
        "ufpa_id": ufpa.pk,
        "formulario_id": 21,
        "formulario_nome": "Diagnóstico produtivo",
        "formulario_versao": "1.0",
        "respondente": "Técnico de Campo",
        "status": "submetido",
        "respostas_json": {"atividade_principal": "Agricultura"},
        "origem": "web",
        "contract_version": "1.0",
        "resposta_id_origem": "web-a1b2c3",
    }
    payload.update(overrides)
    return payload


def test_list_returns_responses_in_reverse_chronological_order(auth_client, ufpa):
    oldest = FormResponseFactory(ufpa=ufpa, data_preenchimento=aware(2026, 1, 1))
    newest = FormResponseFactory(ufpa=ufpa, data_preenchimento=aware(2026, 3, 1))

    response = auth_client.get(list_url(ufpa))

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [newest.pk, oldest.pk]


def test_list_filters_by_formulario_id(auth_client, ufpa):
    expected = FormResponseFactory(ufpa=ufpa, formulario_id=12)
    FormResponseFactory(ufpa=ufpa, formulario_id=13)

    response = auth_client.get(list_url(ufpa), {"formulario_id": 12})

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [expected.pk]


def test_list_filters_by_completion_period(auth_client, ufpa):
    before = FormResponseFactory(ufpa=ufpa, data_preenchimento=aware(2026, 1, 10))
    expected = FormResponseFactory(ufpa=ufpa, data_preenchimento=aware(2026, 2, 15))
    after = FormResponseFactory(ufpa=ufpa, data_preenchimento=aware(2026, 3, 10))

    response = auth_client.get(
        list_url(ufpa),
        {"data_inicio": "2026-02-01", "data_fim": "2026-02-28"},
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response_results(response)]
    assert ids == [expected.pk]
    assert before.pk not in ids
    assert after.pk not in ids


def test_list_filters_by_respondente_isnull_true(auth_client, ufpa):
    anonima = FormResponseFactory(ufpa=ufpa, respondente=None)
    FormResponseFactory(ufpa=ufpa, respondente="Maria Silva")

    response = auth_client.get(list_url(ufpa), {"respondente_isnull": "true"})

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [anonima.pk]


def test_list_filters_by_respondente_isnull_false(auth_client, ufpa):
    identificada = FormResponseFactory(ufpa=ufpa, respondente="Maria Silva")
    FormResponseFactory(ufpa=ufpa, respondente=None)

    response = auth_client.get(list_url(ufpa), {"respondente_isnull": "false"})

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [identificada.pk]


def test_respondente_isnull_combines_with_formulario_and_period(auth_client, ufpa):
    esperada = FormResponseFactory(
        ufpa=ufpa,
        formulario_id=30,
        respondente=None,
        data_preenchimento=aware(2026, 2, 15),
    )
    FormResponseFactory(
        ufpa=ufpa, formulario_id=30, respondente="Maria Silva",
        data_preenchimento=aware(2026, 2, 15),
    )
    FormResponseFactory(
        ufpa=ufpa, formulario_id=31, respondente=None,
        data_preenchimento=aware(2026, 2, 15),
    )
    FormResponseFactory(
        ufpa=ufpa, formulario_id=30, respondente=None,
        data_preenchimento=aware(2026, 5, 1),
    )

    response = auth_client.get(
        list_url(ufpa),
        {
            "formulario_id": 30,
            "respondente_isnull": "true",
            "data_inicio": "2026-02-01",
            "data_fim": "2026-02-28",
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [esperada.pk]


def test_respondente_isnull_combines_with_respondente_text_search(auth_client, ufpa):
    esperada = FormResponseFactory(ufpa=ufpa, respondente="Maria Silva Souza")
    FormResponseFactory(ufpa=ufpa, respondente="Maria Aparecida")
    FormResponseFactory(ufpa=ufpa, respondente=None)

    response = auth_client.get(
        list_url(ufpa),
        {"respondente": "silva", "respondente_isnull": "false"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response_results(response)] == [esperada.pk]


def test_list_rejects_non_boolean_respondente_isnull(auth_client, ufpa):
    response = auth_client.get(list_url(ufpa), {"respondente_isnull": "talvez"})

    assert response.status_code == 400


def test_list_preserves_null_respondent(auth_client, ufpa):
    form_response = FormResponseFactory(ufpa=ufpa, respondente=None)

    response = auth_client.get(list_url(ufpa))

    assert response.status_code == 200
    item = next(item for item in response_results(response) if item["id"] == form_response.pk)
    assert item["respondente"] is None


def test_adt_cannot_list_responses_from_another_territory(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    ufpa_ce = UFPAFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    FormResponseFactory(ufpa=ufpa_ce)

    response = auth_client_adt_rn.get(list_url(ufpa_ce))

    assert response.status_code == 404


def test_detail_returns_complete_response_json(auth_client, ufpa):
    respostas_json = {"secao": {"pergunta": ["sim", "não"]}}
    form_response = FormResponseFactory(ufpa=ufpa, respostas_json=respostas_json)

    response = auth_client.get(detail_url(ufpa, form_response))

    assert response.status_code == 200
    assert response.data["id"] == form_response.pk
    assert response.data["respostas_json"] == respostas_json


def test_detail_returns_404_when_response_belongs_to_another_ufpa(auth_client, ufpa, outra_ufpa):
    other_response = FormResponseFactory(ufpa=outra_ufpa)

    response = auth_client.get(detail_url(ufpa, other_response))

    assert response.status_code == 404


def test_adt_cannot_retrieve_response_from_another_territory(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    ufpa_ce = UFPAFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    form_response = FormResponseFactory(ufpa=ufpa_ce)

    response = auth_client_adt_rn.get(detail_url(ufpa_ce, form_response))

    assert response.status_code == 404


def test_receive_response_creates_and_lists_form_response(auth_client, ufpa):
    response = auth_client.post(RECEIVE_URL, receive_payload(ufpa), format="json")

    assert response.status_code == 201
    form_response = FormResponse.objects.get(pk=response.data["id"])
    assert form_response.ufpa == ufpa
    assert form_response.contract_version == "1.0"
    assert form_response.resposta_id_origem == "web-a1b2c3"

    listed = auth_client.get(list_url(ufpa))
    assert form_response.pk in [item["id"] for item in response_results(listed)]


def test_receive_response_rejects_unknown_ufpa(auth_client, ufpa):
    response = auth_client.post(
        RECEIVE_URL,
        receive_payload(ufpa, ufpa_id=999999),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["ufpa_id"] == ["UFPA não encontrada ou sem permissão de acesso."]


def test_receive_response_is_idempotent(auth_client, ufpa):
    payload = receive_payload(ufpa)

    created = auth_client.post(RECEIVE_URL, payload, format="json")
    retried = auth_client.post(RECEIVE_URL, payload, format="json")

    assert created.status_code == 201
    assert retried.status_code == 200
    assert retried.data["id"] == created.data["id"]
    assert FormResponse.objects.filter(resposta_id_origem="web-a1b2c3").count() == 1


def test_receive_response_keeps_sca_origin(auth_client, ufpa):
    response = auth_client.post(
        RECEIVE_URL,
        receive_payload(ufpa, origem="sca", resposta_id_origem="sca-a1b2c3"),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["origem"] == FormResponse.Origem.SCA
