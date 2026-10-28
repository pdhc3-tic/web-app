"""`/api/v1/sgd/limites-individuais/`: edição só do valor, sem perder reserva concorrente."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
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


def _com_saldo(limite, *, comprometido, executado="0"):
    DemandIndividualLimit.objects.filter(pk=limite.pk).update(
        valor_comprometido=Decimal(comprometido), valor_executado=Decimal(executado),
    )


def test_patch_nao_reduz_o_limite_abaixo_do_comprometido_e_executado(auth_client_super_admin, limite_individual_rn):
    _com_saldo(limite_individual_rn, comprometido="3000", executado="500")

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"valor_limite": "3499.99"})

    assert resposta.status_code == 400
    assert resposta.data["valor_limite"] == [
        "Não pode ser reduzido abaixo do já comprometido e executado: R$ 3.500,00."
    ]
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("5000")


def test_patch_reduz_ate_o_comprometido_e_executado(auth_client_super_admin, limite_individual_rn):
    _com_saldo(limite_individual_rn, comprometido="3000", executado="500")

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"valor_limite": "3500"})

    assert resposta.status_code == 200, resposta.data


def test_patch_aumenta_limite_que_ja_estava_abaixo_do_comprometido(auth_client_super_admin, limite_individual_rn):
    """Depois de um excedente autorizado, o comprometido passa do limite: aumentar
    sem cobrir tudo ainda melhora o saldo."""
    _com_saldo(limite_individual_rn, comprometido="6000")

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"valor_limite": "5500"})

    assert resposta.status_code == 200, resposta.data


def test_create_nao_aceita_limite_negativo(auth_client_super_admin, solicitante_rn, rubrica_diarias):
    resposta = auth_client_super_admin.post(URL, {
        "solicitante": solicitante_rn.pk, "rubrica": rubrica_diarias.pk, "valor_limite": "-1",
    }, format="json")

    assert resposta.status_code == 400
    assert "valor_limite" in resposta.data


def test_create_e_patch_ficam_na_auditoria(auth_client_super_admin, solicitante_rn, rubrica_diarias, usuario_super_admin):
    criado = auth_client_super_admin.post(URL, {
        "solicitante": solicitante_rn.pk, "rubrica": rubrica_diarias.pk, "valor_limite": "1000",
    }, format="json")
    assert criado.status_code == 201, criado.data
    limite = DemandIndividualLimit.objects.get(pk=criado.data["id"])

    assert _patch(auth_client_super_admin, limite, {"valor_limite": "1500"}).status_code == 200
    assert _patch(auth_client_super_admin, limite, {"valor_limite": "1500"}).status_code == 200

    eventos = AuditLog.objects.filter(entidade="DemandIndividualLimit", entidade_id=str(limite.pk)).order_by("id")
    assert [e.acao for e in eventos] == ["limite_individual.criado", "limite_individual.alterado"]
    alteracao = eventos.last()
    assert alteracao.user == usuario_super_admin
    assert alteracao.valores_anteriores == {"valor_limite": "1000.00"}
    assert alteracao.valores_novos["valor_limite"] == "1500.00"


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
