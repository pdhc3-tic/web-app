from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.sgp.tests.factories import FormResponseFactory, UPFFactory


pytestmark = pytest.mark.django_db


def options_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/opcoes/"


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


def test_upf_without_responses_returns_empty_list(auth_client, upf):
    response = auth_client.get(options_url(upf))

    assert response.status_code == 200
    assert response.data == []


def test_returns_each_formulario_once_ordered_by_name(auth_client, upf):
    FormResponseFactory(upf=upf, formulario_id=20, formulario_nome="Zebra", formulario_versao="1.0")
    FormResponseFactory(upf=upf, formulario_id=20, formulario_nome="Zebra", formulario_versao="1.0")
    FormResponseFactory(upf=upf, formulario_id=21, formulario_nome="Abelha", formulario_versao="1.0")

    response = auth_client.get(options_url(upf))

    assert response.status_code == 200
    assert response.data == [
        {"formulario_id": 21, "formulario_nome": "Abelha", "formulario_versao": "1.0"},
        {"formulario_id": 20, "formulario_nome": "Zebra", "formulario_versao": "1.0"},
    ]


def test_option_outside_first_page_of_list_is_still_returned(auth_client, upf):
    # 25 é o page_size de HistoricoPagination — o formulário antigo só
    # aparece na 2ª página da listagem, mas deve estar nas opções mesmo assim.
    for i in range(25):
        FormResponseFactory(
            upf=upf,
            formulario_id=1,
            formulario_nome="Diagnóstico produtivo",
            data_preenchimento=timezone.now() - timedelta(days=i),
        )
    antigo = FormResponseFactory(
        upf=upf,
        formulario_id=2,
        formulario_nome="Perfil socioeconômico",
        data_preenchimento=timezone.now() - timedelta(days=200),
    )

    listagem = auth_client.get(f"/api/v1/sgp/upfs/{upf.pk}/formularios/")
    assert antigo.pk not in [item["id"] for item in listagem.data["results"]]

    response = auth_client.get(options_url(upf))

    assert response.status_code == 200
    assert {"formulario_id": 2, "formulario_nome": "Perfil socioeconômico", "formulario_versao": "1.0"} in response.data


def test_options_are_not_affected_by_other_query_params(auth_client, upf):
    FormResponseFactory(
        upf=upf, formulario_id=1, formulario_nome="Diagnóstico produtivo",
        data_preenchimento=aware(2026, 1, 1),
    )
    FormResponseFactory(
        upf=upf, formulario_id=2, formulario_nome="Perfil socioeconômico",
        data_preenchimento=aware(2026, 6, 1),
    )

    response = auth_client.get(
        options_url(upf),
        {"data_inicio": "2026-01-01", "data_fim": "2026-01-31"},
    )

    assert response.status_code == 200
    assert {item["formulario_id"] for item in response.data} == {1, 2}


def test_options_scoped_to_requested_upf(auth_client, upf, outra_upf):
    FormResponseFactory(upf=outra_upf, formulario_id=99, formulario_nome="De outra UPF")

    response = auth_client.get(options_url(upf))

    assert response.status_code == 200
    assert response.data == []


def test_adt_cannot_read_options_from_another_territory(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    FormResponseFactory(upf=upf_ce)

    response = auth_client_adt_rn.get(options_url(upf_ce))

    assert response.status_code == 404
