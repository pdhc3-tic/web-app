from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def test_saldo_bloqueio_individual_traz_acao_sugerida(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "100"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["disponivel"] is False
    assert data["individual"]["acao_sugerida"] == "solicitar_recurso_extra"
    # Sem limite configurado a orientação é a mesma da trava individual
    # esgotada (SGP §6.5).
    assert "Solicitar recurso extra" in data["individual"]["motivo_bloqueio"]


def test_saldo_bloqueio_territorial_traz_acao_sugerida(
    auth_client_solicitante, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("100"), valor_comprometido=Decimal("100"),
    )
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "50"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["territorial"]["disponivel"] is False
    assert data["territorial"]["acao_sugerida"] == "acionar_articulador"
    assert "Acione o Articulador Estadual" in data["territorial"]["motivo_bloqueio"]
    assert "Território esgotado" in data["territorial"]["motivo_bloqueio"]
    assert "R$ 0,00 disponível, R$ 50,00 solicitado" in data["territorial"]["motivo_bloqueio"]
    # Saldo zerado: esgotado de vez, não só "para este valor".
    assert "para este valor" not in data["territorial"]["motivo_bloqueio"]


def test_saldo_sem_alocacao_territorial_orienta_sem_dizer_que_esgotou(
    auth_client_solicitante, activity_rn, rubrica_diarias, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "50"},
    )
    assert response.status_code == 200
    territorial = response.json()["territorial"]
    assert territorial["disponivel"] is False
    assert territorial["motivo_bloqueio"].startswith(
        "Nenhuma alocação orçamentária territorial encontrada: R$ 0,00 disponível, R$ 50,00 solicitado."
    )
    assert "Acione o Articulador Estadual" in territorial["motivo_bloqueio"]
    assert "esgotad" not in territorial["motivo_bloqueio"]
    assert territorial["semaforo_atual"] is None


def test_saldo_disponivel_traz_semaforo(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["semaforo_atual"] == "verde"
    assert data["individual"]["semaforo_apos"] == "verde"
    assert data["territorial"]["semaforo_atual"] == "verde"
    assert data["territorial"]["semaforo_apos"] == "verde"
    assert data["individual"]["acao_sugerida"] is None
    assert data["territorial"]["acao_sugerida"] is None
    assert data["individual"]["motivo_bloqueio"] is None
    assert data["territorial"]["motivo_bloqueio"] is None


def test_saldo_semaforo_apos_mostra_mudanca_de_faixa(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    # Limite individual de 5.000: 3.600 leva de 0% a 72% (cruza 70%). Pool
    # territorial de 10.000: os mesmos 3.600 dão 36%, continua verde.
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "3600"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["individual"]["disponivel"] is True
    assert data["individual"]["semaforo_atual"] == "verde"
    assert data["individual"]["semaforo_apos"] == "amarelo"
    assert data["territorial"]["semaforo_atual"] == "verde"
    assert data["territorial"]["semaforo_apos"] == "verde"


def test_saldo_semaforo_segue_limiares_configurados_no_core(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="budget_alert_yellow_pct", defaults={"valor": "30", "tipo": TipoConfiguracao.INTEGER},
    )
    try:
        response = auth_client_solicitante.get(
            "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "3600"},
        )
        assert response.status_code == 200
        assert response.json()["territorial"]["semaforo_apos"] == "amarelo"
    finally:
        # Cache de SystemConfig não é transacional — limpa pra não vazar
        # o limiar de 30% pros testes seguintes.
        cache.delete("system_config:budget_alert_yellow_pct")


def test_saldo_limite_individual_insuficiente_orienta_recurso_extra(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "6000"},
    )
    assert response.status_code == 200
    individual = response.json()["individual"]
    assert individual["disponivel"] is False
    assert "R$ 5.000,00 disponível, R$ 6.000,00 solicitado" in individual["motivo_bloqueio"]
    assert "Solicitar recurso extra" in individual["motivo_bloqueio"]


def test_saldo_por_tipo_resolve_a_rubrica_do_mapeamento(
    auth_client_solicitante, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    por_tipo = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "tipo": "diaria", "valor": "10"},
    )
    por_rubrica = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "10"},
    )
    assert por_tipo.status_code == 200
    assert por_tipo.json() == por_rubrica.json()
    assert por_tipo.json()["rubrica_slug"] == "diarias"
    assert por_tipo.json()["rubrica_nome"] == "Diárias"


@pytest.mark.parametrize("params", [
    {"valor": "10"},
    {"valor": "10", "tipo": "diaria", "rubrica": "diarias"},
])
def test_saldo_exige_exatamente_um_entre_rubrica_e_tipo(auth_client_solicitante, activity_rn, rubrica_diarias, params):
    response = auth_client_solicitante.get("/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, **params})
    assert response.status_code == 400


def test_saldo_tipo_invalido_retorna_400(auth_client_solicitante, activity_rn):
    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "tipo": "hospedagem", "valor": "10"},
    )
    assert response.status_code == 400
    assert "tipo" in response.json()


def test_saldo_tipo_sem_rubrica_mapeada_retorna_400_em_tipo(auth_client_solicitante, activity_rn, rubrica_diarias):
    from apps.sgd.models import DemandTypeRubricaMapping

    DemandTypeRubricaMapping.objects.filter(tipo="veiculo").delete()

    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "tipo": "veiculo", "valor": "10"},
    )
    assert response.status_code == 400
    assert "tipo" in response.json()


def test_saldo_com_perfil_sem_territorio_responde_403_com_a_mensagem_do_motor(
    auth_client_solicitante, solicitante_rn, activity_rn, rubrica_diarias, allocation_territorial_rn,
):
    solicitante_rn.profiles.update(territorio=None)

    response = auth_client_solicitante.get(
        "/api/v1/sgd/saldo/", {"activity_id": activity_rn.pk, "rubrica": rubrica_diarias.slug, "valor": "100"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Perfil sem estado/território específico — não é possível resolver um único nível "
                  "para a consulta de saldo.",
    }
