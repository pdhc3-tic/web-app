"""A notificação de semáforo do SGD segue o alerta orçamentário do SGP."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models.notifications import TipoNotificacao
from apps.sgd.services import balance as balance_service
from apps.sgd.tests.concorrencia import intercalar
from apps.sgp.budget import alertas
from apps.sgp.models import BudgetAlert, BudgetPool, SpendingLimit
from apps.sgp.tasks import check_budget_thresholds
from apps.sgp.tests.factories import SpendingLimitFactory

EVENTO_SGD = "demand_semaforo_mudou"


@pytest.fixture(autouse=True)
def sem_envio_de_email():
    with patch("apps.core.tasks.notifications.send_email_notification.delay"):
        yield


def _limite(solicitante, rubrica, valor):
    return SpendingLimitFactory(user=solicitante, rubrica=rubrica, valor_limite=Decimal(valor))


def _canais(usuario, evento=EVENTO_SGD):
    return set(usuario.notifications.filter(evento=evento).values_list("tipo", flat=True))


@pytest.mark.django_db
def test_vermelho_no_limite_abre_o_alerta_e_avisa_tambem_o_articulador(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, allocation_territorial_rn, rubrica_diarias,
):
    limite = _limite(solicitante_rn, rubrica_diarias, "1100")

    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    alerta = BudgetAlert.objects.get(escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk)
    assert alerta.faixa == "vermelho"
    assert alerta.usuarios_alertados_ids == sorted([solicitante_rn.pk, usuario_articulador_rn.pk])
    assert _canais(solicitante_rn) == {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}
    assert _canais(usuario_articulador_rn) == {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}
    notificacao = solicitante_rn.notifications.filter(evento=EVENTO_SGD).first()
    assert rubrica_diarias.nome in notificacao.titulo
    assert "100,00" in notificacao.mensagem


@pytest.mark.django_db
def test_amarelo_no_limite_avisa_so_o_solicitante_e_so_no_app(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, allocation_territorial_rn, rubrica_diarias,
):
    _limite(solicitante_rn, rubrica_diarias, "1300")

    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    assert _canais(solicitante_rn) == {TipoNotificacao.IN_APP}
    assert not usuario_articulador_rn.notifications.filter(evento=EVENTO_SGD).exists()


@pytest.mark.django_db
def test_a_tarefa_nao_notifica_de_novo_o_que_a_movimentacao_ja_avisou(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, rubrica_diarias,
):
    limite = _limite(solicitante_rn, rubrica_diarias, "1100")
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    total = solicitante_rn.notifications.count()

    assert check_budget_thresholds(limite_id=limite.pk) == 0

    assert solicitante_rn.notifications.count() == total
    assert not solicitante_rn.notifications.filter(evento=alertas.EVENTO_SEMAFORO).exists()


@pytest.mark.django_db
def test_liberar_a_reserva_resolve_o_alerta_na_avaliacao_da_tarefa(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, rubrica_diarias,
):
    limite = _limite(solicitante_rn, rubrica_diarias, "1100")
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.refresh_from_db()

    balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Cancelada.")
    check_budget_thresholds(limite_id=limite.pk)

    assert BudgetAlert.objects.get(escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk).resolvido_em is not None


@pytest.mark.django_db(transaction=True)
def test_tarefa_espera_a_movimentacao_e_nao_duplica_o_alerta(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, rubrica_diarias,
):
    limite = _limite(solicitante_rn, rubrica_diarias, "1100")

    def reservar(pausa):
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
        pausa()

    _, erros = intercalar(reservar, lambda: alertas.avaliar_semaforo(SpendingLimit, limite.pk))

    assert erros == {}
    assert BudgetAlert.objects.filter(escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk).count() == 1
    assert not solicitante_rn.notifications.filter(evento=alertas.EVENTO_SEMAFORO).exists()
    assert BudgetPool.objects.get(pk=allocation_territorial_rn.pk).valor_comprometido == Decimal("1000")
