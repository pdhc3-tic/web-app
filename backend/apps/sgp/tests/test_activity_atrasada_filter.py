"""Filtro `?atrasada=` da listagem de atividades.

A contagem do filtro precisa bater com o campo `atrasada` de cada item: é o
que o card "Atrasadas" do dashboard exibe.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgp/atividades/"


def _atividade(dias_fim, status_atividade, **kwargs):
    fim = timezone.now() + timedelta(days=dias_fim)
    return ActivityFactory(
        data_inicio=fim - timedelta(hours=4), data_fim=fim, status=status_atividade, **kwargs
    )


@pytest.fixture
def cenario():
    return {
        "atrasada_em_andamento": _atividade(-3, "em_andamento"),
        "atrasada_adiada": _atividade(-10, "adiada"),
        "passada_concluida": _atividade(-3, "concluido"),
        "passada_cancelada": _atividade(-3, "cancelada"),
        "futura_planejada": _atividade(5, "planejado"),
    }


def _ids(response):
    return {item["id"] for item in response.data["results"]}


def test_atrasada_true_traz_so_atrasadas(auth_client_super_admin, cenario):
    response = auth_client_super_admin.get(URL, {"atrasada": "true", "page_size": 50})

    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == {
        cenario["atrasada_em_andamento"].pk,
        cenario["atrasada_adiada"].pk,
    }
    assert all(item["atrasada"] for item in response.data["results"])


def test_atrasada_false_e_o_complemento(auth_client_super_admin, cenario):
    total = auth_client_super_admin.get(URL).data["count"]
    atrasadas = auth_client_super_admin.get(URL, {"atrasada": "true"}).data["count"]
    nao_atrasadas = auth_client_super_admin.get(URL, {"atrasada": "false", "page_size": 50})

    assert atrasadas + nao_atrasadas.data["count"] == total
    assert not any(item["atrasada"] for item in nao_atrasadas.data["results"])


def test_contagem_com_page_size_1_bate_com_a_lista(auth_client_super_admin, cenario):
    contagem = auth_client_super_admin.get(URL, {"atrasada": "true", "page_size": 1}).data["count"]
    lista = auth_client_super_admin.get(URL, {"atrasada": "true", "page_size": 50}).data

    assert contagem == len(lista["results"]) == 2


def test_valor_invalido_retorna_400(auth_client_super_admin, cenario):
    response = auth_client_super_admin.get(URL, {"atrasada": "talvez"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_adt_so_conta_atrasadas_do_proprio_territorio(auth_client_adt_rn, municipio_rn, municipio_ce):
    no_territorio = _atividade(-3, "em_andamento", municipio=municipio_rn)
    _atividade(-3, "em_andamento", municipio=municipio_ce)

    response = auth_client_adt_rn.get(URL, {"atrasada": "true"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert _ids(response) == {no_territorio.pk}
