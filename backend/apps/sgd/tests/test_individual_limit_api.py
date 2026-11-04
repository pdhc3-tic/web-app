"""`/api/v1/sgd/limites-individuais/`: edição só do valor, sem perder reserva concorrente."""
from decimal import Decimal

import pytest
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.tests.factories import UserFactory
from apps.sgd.serializers.individual_limit import DemandIndividualLimitSerializer
from apps.sgd.tests.concorrencia import intercalar
from apps.sgp.budget import limites
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, SpendingLimitFactory
from apps.sgp.models import SpendingLimit

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/limites-individuais/"


def _patch(cliente, limite, corpo):
    return cliente.patch(f"{URL}{limite.pk}/", corpo, format="json")


def test_patch_altera_so_o_valor_limite(auth_client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("700"))

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
    assert limite_individual_rn.user_id != usuario_ugp.pk


def test_patch_com_a_mesma_rubrica_e_aceito(auth_client_super_admin, limite_individual_rn):
    resposta = _patch(
        auth_client_super_admin, limite_individual_rn,
        {"rubrica": limite_individual_rn.rubrica_id, "valor_limite": "6000"},
    )

    assert resposta.status_code == 200, resposta.data


def _com_saldo(limite, *, comprometido, executado="0"):
    SpendingLimit.objects.filter(pk=limite.pk).update(
        valor_comprometido=Decimal(comprometido), valor_executado=Decimal(executado),
    )


def test_patch_reduz_abaixo_do_comprometido_preservando_o_saldo(auth_client_super_admin, limite_individual_rn):
    """O rebaixamento não invalida o que já foi autorizado: o novo teto vale para as próximas reservas."""
    _com_saldo(limite_individual_rn, comprometido="3000", executado="500")

    resposta = _patch(auth_client_super_admin, limite_individual_rn, {"valor_limite": "1000"})

    assert resposta.status_code == 200, resposta.data
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("1000")
    assert limite_individual_rn.valor_comprometido == Decimal("3000")
    assert limite_individual_rn.saldo_disponivel == Decimal("-2500")


def test_patch_nao_aceita_o_id_de_um_padrao_por_perfil(auth_client_super_admin, solicitante_rn, rubrica_diarias):
    from datetime import date

    from apps.sgp.budget.limites import FIM_EM_ABERTO

    padrao = SpendingLimit.objects.create(
        escopo=SpendingLimit.Escopo.PERFIL, perfil=solicitante_rn.profiles.get().perfil, rubrica=rubrica_diarias,
        valor_limite=Decimal("1000"), periodo_inicio=date(2026, 1, 1), periodo_fim=FIM_EM_ABERTO,
    )

    resposta = _patch(auth_client_super_admin, padrao, {"valor_limite": "9000"})

    assert resposta.status_code == 404
    padrao.refresh_from_db()
    assert padrao.valor_limite == Decimal("1000")


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
    limite = SpendingLimit.objects.get(pk=criado.data["id"])

    assert _patch(auth_client_super_admin, limite, {"valor_limite": "1500"}).status_code == 200
    assert _patch(auth_client_super_admin, limite, {"valor_limite": "1500"}).status_code == 200

    eventos = AuditLog.objects.filter(entidade="SpendingLimit", entidade_id=str(limite.pk)).order_by("id")
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
        "solicitante": limite_individual_rn.user_id, "rubrica": limite_individual_rn.rubrica_id,
        "valor_limite": "100",
    }, format="json")

    assert resposta.status_code == 400
    assert "rubrica" in resposta.data
    assert SpendingLimit.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_patch_concorrente_com_reserva_nao_apaga_o_comprometido(limite_individual_rn, usuario_super_admin):
    def reservar(pausa):
        limite = SpendingLimit.objects.select_for_update(of=("self",)).get(pk=limite_individual_rn.pk)
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


@pytest.mark.django_db(transaction=True)
def test_aumentos_simultaneos_nao_passam_do_pool(solicitante_rn, rubrica_diarias, territory_rn, usuario_super_admin):
    """O pool fica travado até o commit: o segundo aumento espera e já vê o primeiro na soma."""
    outro = UserFactory(profiles=[(solicitante_rn.profiles.first().perfil, territory_rn)])
    # 700 + 400 cabe; 700 + 700 não. Sem o lock, cada um somaria o outro ainda em 400 e os dois passariam.
    BudgetPoolFactory(rubrica=rubrica_diarias, territorio=territory_rn, valor_alocado=Decimal("1200"))
    linha = SpendingLimitFactory(user=solicitante_rn, rubrica=rubrica_diarias, valor_limite=Decimal("400"))
    linha_do_outro = SpendingLimitFactory(user=outro, rubrica=rubrica_diarias, valor_limite=Decimal("400"))
    SystemConfig.objects.update_or_create(
        chave="budget_overallocation_allowed", defaults={"valor": "False", "tipo": TipoConfiguracao.BOOLEAN},
    )
    cache.delete("system_config:budget_overallocation_allowed")

    def aumentar(limite):
        return limites.alterar_sobrescrita(
            limite.pk, valor_limite=Decimal("700"), justificativa="Aumento.", usuario=usuario_super_admin,
        )

    def segura(pausa):
        aumentar(linha)
        pausa()

    try:
        _, erros = intercalar(segura, lambda: aumentar(linha_do_outro))
    finally:
        cache.delete("system_config:budget_overallocation_allowed")

    assert isinstance(erros["espera"], ValidationError)
    linha.refresh_from_db()
    linha_do_outro.refresh_from_db()
    assert (linha.valor_limite, linha_do_outro.valor_limite) == (Decimal("700"), Decimal("400"))
