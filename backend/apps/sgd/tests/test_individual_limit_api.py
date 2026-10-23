"""`/api/v1/sgd/limites-individuais/`: edição só do valor, sem perder reserva concorrente."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.sgd.models import DemandIndividualLimit
from apps.sgd.serializers.individual_limit import DemandIndividualLimitSerializer
from apps.sgd.tests.concorrencia import intercalar
from apps.sgp.tests.factories import BudgetRubricaFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/limites-individuais/"


def _patch(cliente, limite, corpo):
    return cliente.patch(f"{URL}{limite.pk}/", corpo, format="json")


def test_patch_altera_so_o_valor_limite(auth_client_super_admin, limite_individual_rn):
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("700"))

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"valor_limite": "8000"})

    assert resposta.status_code == 200, resposta.data
    limite_individual_rn.refresh_from_db()
    assert (limite_individual_rn.valor_limite, limite_individual_rn.valor_comprometido) == (
        Decimal("8000"), Decimal("700"),
    )


def test_patch_nao_move_o_limite_para_outra_rubrica(auth_client_super_admin, limite_individual_rn):
    outra = BudgetRubricaFactory(slug="outra-rubrica-limite")

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"rubrica": outra.pk})

    assert resposta.status_code == 400
    assert "rubrica" in resposta.data
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.rubrica_id != outra.pk


def test_patch_nao_move_o_limite_para_outro_solicitante(
    auth_client_super_admin, limite_individual_rn, usuario_ugp,
):
    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"solicitante": usuario_ugp.pk})

    assert resposta.status_code == 400
    assert "solicitante" in resposta.data
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.solicitante_id != usuario_ugp.pk


def test_patch_com_a_mesma_rubrica_e_aceito(auth_client_super_admin, limite_individual_rn):
    resposta = _patch(
        auth_client_super_admin, limite_individual_rn,
        {"rubrica": limite_individual_rn.rubrica_id, "valor_limite": "6000"},
    )

    assert resposta.status_code == 200, resposta.data


def test_create_concorrente_com_limite_ja_criado_responde_400(
    auth_client_super_admin, limite_individual_rn, monkeypatch,
):
    """A validação de unicidade passa quando o outro insert ainda não commitou;
    sem ela, o insert bate na constraint, como na corrida."""
    monkeypatch.setattr(DemandIndividualLimitSerializer, "get_validators", lambda self: [])

    resposta = auth_client_super_admin.post(URL, {
        "solicitante": limite_individual_rn.solicitante_id, "rubrica": limite_individual_rn.rubrica_id,
        "valor_limite": "100",
    }, format="json")

    assert resposta.status_code == 400
    assert "rubrica" in resposta.data
    assert DemandIndividualLimit.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_patch_concorrente_com_reserva_nao_apaga_o_comprometido(limite_individual_rn, usuario_super_admin):
    def reservar(pausa):
        limite = DemandIndividualLimit.objects.select_for_update().get(pk=limite_individual_rn.pk)
        pausa()
        limite.valor_comprometido = Decimal("700")
        limite.save(update_fields=["valor_comprometido"])

    def editar():
        cliente = APIClient()
        cliente.force_authenticate(user=usuario_super_admin)
        return _patch(cliente, limite_individual_rn, {"valor_limite": "8000"})

    resultados, erros = intercalar(reservar, editar)

    assert erros == {}
    assert resultados["espera"].status_code == 200
    limite_individual_rn.refresh_from_db()
    assert (limite_individual_rn.valor_limite, limite_individual_rn.valor_comprometido) == (
        Decimal("8000"), Decimal("700"),
    )
