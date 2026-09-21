from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models.notifications import TipoNotificacao
from apps.sgd.services import approval as approval_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service

pytestmark = pytest.mark.django_db


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_submissao_notifica_articulador_do_estado(
    mocked_delay, demand_request_rn, solicitante_rn, usuario_articulador_rn,
    allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)

    notifs = usuario_articulador_rn.notifications.filter(evento="demand_submetida")
    assert notifs.filter(tipo=TipoNotificacao.EMAIL).exists()
    assert notifs.filter(tipo=TipoNotificacao.IN_APP).exists()


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_devolucao_notifica_solicitante(mocked_delay, demand_rascunho_rn, solicitante_rn, usuario_articulador_rn):
    demand_rascunho_rn.status = "submetida"
    demand_rascunho_rn.save(update_fields=["status"])

    approval_service.devolver(demand_rascunho_rn, responsavel=usuario_articulador_rn, justificativa="Falta anexo.")

    assert solicitante_rn.notifications.filter(evento="demand_devolvida").exists()


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_pre_autorizacao_notifica_ugp(mocked_delay, demand_rascunho_rn, usuario_articulador_rn, usuario_ugp):
    demand_rascunho_rn.status = "submetida"
    demand_rascunho_rn.save(update_fields=["status"])

    approval_service.pre_autorizar(demand_rascunho_rn, responsavel=usuario_articulador_rn)

    assert usuario_ugp.notifications.filter(evento="demand_pre_autorizada").exists()


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_autorizacao_notifica_solicitante_e_fgd(
    mocked_delay, demand_request_rn, solicitante_rn, usuario_ugp, usuario_fgd,
    allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    approval_service.autorizar(demand, responsavel=usuario_ugp)

    assert solicitante_rn.notifications.filter(evento="demand_autorizada").exists()
    assert usuario_fgd.notifications.filter(evento="demand_autorizada").exists()


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_atender_notifica_apenas_in_app(mocked_delay, demand_rascunho_rn, solicitante_rn, usuario_fgd):
    demand_rascunho_rn.status = "autorizada"
    demand_rascunho_rn.save(update_fields=["status"])

    approval_service.atender(demand_rascunho_rn, responsavel=usuario_fgd)

    notifs = solicitante_rn.notifications.filter(evento="demand_em_atendimento")
    assert notifs.count() == 1
    assert notifs.first().tipo == TipoNotificacao.IN_APP


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_reservar_notifica_quando_semaforo_individual_piora(
    mocked_delay, demand_request_rn, solicitante_rn, allocation_territorial_rn,
):
    from apps.sgd.tests.factories import DemandIndividualLimitFactory

    # limite apertado (1000/1100 ≈ 91%) — cruza de verde direto pra vermelho.
    DemandIndividualLimitFactory(
        solicitante=solicitante_rn, rubrica=demand_request_rn.rubrica, valor_limite=Decimal("1100"),
    )

    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    assert solicitante_rn.notifications.filter(evento="demand_semaforo_mudou").exists()


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_reservar_nao_notifica_quando_semaforo_nao_piora(
    mocked_delay, demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    assert not solicitante_rn.notifications.filter(evento="demand_semaforo_mudou").exists()


def test_alerta_rubrica_fora_do_previsto_aparece_no_payload(demand_request_rn, rubrica_diarias):
    from apps.sgd.serializers.demand_request import DemandRequestSerializer
    from apps.sgp.tests.factories import BudgetRubricaFactory

    acao = demand_request_rn.demanda.activity.acao
    acao.rubricas_previstas.set([rubrica_diarias])
    demand_request_rn.rubrica = BudgetRubricaFactory(slug="rubrica-inesperada-para-diaria")
    demand_request_rn.save(update_fields=["rubrica"])

    data = DemandRequestSerializer(demand_request_rn).data

    assert data["alerta_rubrica_fora_do_previsto"] is True


def test_alerta_rubrica_fora_do_previsto_sem_previsao_cadastrada_nao_alerta(demand_request_rn):
    from apps.sgd.serializers.demand_request import DemandRequestSerializer
    from apps.sgp.tests.factories import BudgetRubricaFactory

    # Ação sem `rubricas_previstas` configurada — sem opinião, nunca alerta.
    demand_request_rn.rubrica = BudgetRubricaFactory(slug="rubrica-qualquer")
    demand_request_rn.save(update_fields=["rubrica"])

    data = DemandRequestSerializer(demand_request_rn).data

    assert data["alerta_rubrica_fora_do_previsto"] is False
