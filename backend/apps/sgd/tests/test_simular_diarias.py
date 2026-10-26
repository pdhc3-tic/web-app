"""`GET /api/v1/sgd/config/diarias/simular/`: o valor das diárias antes de salvar."""
from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.services.demand_request import validar_campos_json

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/config/diarias/simular/"


@pytest.fixture
def diaria_a(db):
    def configurar(valor):
        SystemConfig.objects.update_or_create(
            chave="sgd_valor_diaria_padrao", defaults={"valor": valor, "tipo": TipoConfiguracao.STRING},
        )
        cache.delete("system_config:sgd_valor_diaria_padrao")
    yield configurar
    cache.delete("system_config:sgd_valor_diaria_padrao")


def _simular(cliente, municipio, inicio="2026-11-02", fim="2026-11-04"):
    return cliente.get(URL, {"municipio_destino_id": municipio.pk, "data_inicio": inicio, "data_fim": fim})


def test_simula_com_a_regra_de_hoje(auth_client_solicitante, municipio_rn, diaria_a):
    diaria_a("300")

    resposta = _simular(auth_client_solicitante, municipio_rn)

    assert resposta.status_code == 200, resposta.data
    assert resposta.json() == {
        "faixa_destino": {"id": None, "nome": "Valor padrão"},
        "valor_por_diaria": "300.00",
        "numero_diarias": "2.0",
        "valor_total": "600.00",
    }


def test_ida_e_volta_no_mesmo_dia_conta_uma_diaria(auth_client_solicitante, municipio_rn, diaria_a):
    diaria_a("300")

    resposta = _simular(auth_client_solicitante, municipio_rn, inicio="2026-11-02", fim="2026-11-02")

    assert (resposta.json()["numero_diarias"], resposta.json()["valor_total"]) == ("1.0", "300.00")


def test_simulacao_e_gravacao_dao_o_mesmo_valor(auth_client_solicitante, municipio_rn, activity_rn, diaria_a):
    diaria_a("250")
    campos = {
        "beneficiario_nome": "Fulano", "beneficiario_cpf": "52998224725", "beneficiario_cargo": "Técnico",
        "beneficiario_vinculo": "servidor_ufersa", "municipio_destino_id": municipio_rn.pk,
        "data_inicio": "2026-11-02", "data_fim": "2026-11-05", "meio_transporte": "rodoviario",
        "justificativa": "Visita técnica.",
    }

    simulado = _simular(auth_client_solicitante, municipio_rn, inicio="2026-11-02", fim="2026-11-05").json()

    assert Decimal(simulado["valor_total"]) == validar_campos_json("diaria", campos, activity_rn).valor_estimado_auto


def test_sem_valor_configurado_responde_400_com_a_mensagem(auth_client_solicitante, municipio_rn, diaria_a):
    diaria_a("0")

    resposta = _simular(auth_client_solicitante, municipio_rn)

    assert resposta.status_code == 400
    assert "valor_por_diaria" in resposta.data


def test_data_final_antes_da_inicial_responde_400(auth_client_solicitante, municipio_rn, diaria_a):
    diaria_a("300")

    resposta = _simular(auth_client_solicitante, municipio_rn, inicio="2026-11-05", fim="2026-11-02")

    assert resposta.status_code == 400
    assert "data_fim" in resposta.data


def test_municipio_inexistente_responde_400(auth_client_solicitante, diaria_a):
    diaria_a("300")

    resposta = auth_client_solicitante.get(
        URL, {"municipio_destino_id": 999_999, "data_inicio": "2026-11-02", "data_fim": "2026-11-03"},
    )

    assert resposta.status_code == 400
    assert "municipio_destino_id" in resposta.data


def test_municipio_nao_numerico_na_solicitacao_e_erro_do_campo(activity_rn, diaria_a):
    diaria_a("300")
    campos = {
        "beneficiario_nome": "Fulano", "beneficiario_cpf": "52998224725", "beneficiario_cargo": "Técnico",
        "beneficiario_vinculo": "servidor_ufersa", "municipio_destino_id": "abc",
        "data_inicio": "2026-11-02", "data_fim": "2026-11-05", "meio_transporte": "rodoviario",
        "justificativa": "Visita técnica.",
    }

    with pytest.raises(RegraDeNegocio) as excinfo:
        validar_campos_json("diaria", campos, activity_rn)

    assert excinfo.value.campo == "municipio_destino_id"


def test_parametros_obrigatorios(auth_client_solicitante):
    resposta = auth_client_solicitante.get(URL)

    assert resposta.status_code == 400
    assert {"municipio_destino_id", "data_inicio", "data_fim"} <= set(resposta.data)


def test_quem_nao_cria_demanda_nao_simula(auth_client_ugp, municipio_rn, diaria_a):
    diaria_a("300")

    assert _simular(auth_client_ugp, municipio_rn).status_code == 403
