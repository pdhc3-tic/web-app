from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.sgd.models.demand import Demand
from apps.sgd.tasks import check_demand_inactivity_alert
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def _voltar_no_tempo_dias_uteis(demand, dias_uteis: int) -> None:
    """Aproxima dias corridos suficientes pra cobrir `dias_uteis` úteis —
    não precisa ser exato porque os testes usam 4 e 5, bem afastados de um
    fim de semana no meio (ver `_dias_uteis_entre`)."""
    referencia = timezone.now() - timedelta(days=dias_uteis + 2)
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=referencia)


def test_demanda_sem_movimentacao_ha_5_dias_uteis_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")
    _voltar_no_tempo_dias_uteis(demand, 7)  # >= 5 dias úteis com folga

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 1
    notificar.assert_called_once()


def test_demanda_com_4_dias_nao_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")
    Demand.objects.filter(pk=demand.pk).update(status_alterado_em=timezone.now() - timedelta(days=4))

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 0
    notificar.assert_not_called()


def test_demanda_terminal_nunca_dispara(activity_rn):
    demand = DemandFactory(activity=activity_rn, status="concluida")
    _voltar_no_tempo_dias_uteis(demand, 30)

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        check_demand_inactivity_alert()

    notificar.assert_not_called()


def test_demanda_em_rascunho_nunca_dispara(activity_rn):
    """Rascunho nunca foi submetida — não tem etapa aguardando ninguém."""
    demand = DemandFactory(activity=activity_rn, status="rascunho")
    _voltar_no_tempo_dias_uteis(demand, 30)

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 0
    notificar.assert_not_called()


def test_edicao_sem_mudar_status_nao_zera_contagem(activity_rn):
    """Salvar a demanda sem trocar o status (ex.: editar o título) atualiza
    atualizado_em, mas a demanda continua parada na mesma etapa."""
    demand = DemandFactory(activity=activity_rn, status="submetida")
    _voltar_no_tempo_dias_uteis(demand, 7)
    demand.refresh_from_db()
    demand.titulo = "Título corrigido"
    demand.save()

    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 1
    notificar.assert_called_once()


def test_mudanca_de_status_reinicia_contagem(activity_rn, usuario_articulador_rn):
    """Resubmeter/decidir é movimentação — a referência passa a ser a nova
    mudança de status, não a etapa anterior (ex.: uma devolução antiga)."""
    from apps.sgd.services.approval import pre_autorizar

    demand = DemandFactory(activity=activity_rn, status="submetida")
    _voltar_no_tempo_dias_uteis(demand, 10)
    demand.refresh_from_db()

    with patch("apps.sgd.services.notifications.notificar_pre_autorizacao"):
        pre_autorizar(demand, responsavel=usuario_articulador_rn)

    demand.refresh_from_db()
    assert timezone.localdate(demand.status_alterado_em) == timezone.localdate()
    with patch("apps.sgd.tasks.notificar_inatividade") as notificar:
        total = check_demand_inactivity_alert()

    assert total == 0
    notificar.assert_not_called()


def test_nao_notifica_duas_vezes_pelo_mesmo_periodo_parado(activity_rn, usuario_articulador_rn):
    """Rodar a task duas vezes seguidas sobre a mesma demanda parada não pode
    gerar duas notificações do mesmo período de inatividade.
    `usuario_articulador_rn` precisa existir — sem responsável nenhum
    recebendo a notificação, nenhuma `Notification` é criada e a
    deduplicação (que olha pra essas linhas) não teria o que comparar."""
    demand = DemandFactory(activity=activity_rn, status="submetida")
    _voltar_no_tempo_dias_uteis(demand, 7)

    total_1 = check_demand_inactivity_alert()
    total_2 = check_demand_inactivity_alert()

    assert total_1 == 1
    assert total_2 == 0
