"""A notificação de semáforo do SGD segue o alerta orçamentário do SGP."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models.notifications import TipoNotificacao
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services import remanejamento as remanejamento_service
from apps.sgd.tests.concorrencia import intercalar
from apps.sgd.tests.factories import BudgetIncreaseRequestFactory
from apps.sgp.budget import alertas
from apps.sgp.models import BudgetAlert, BudgetPool, BudgetTransfer, SpendingLimit
from apps.sgp.tasks import check_budget_thresholds
from apps.sgp.tests.factories import BudgetPoolFactory, SpendingLimitFactory

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


@pytest.mark.django_db
def test_voltar_de_vermelho_para_amarelo_e_nova_entrada_na_faixa(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, rubrica_diarias,
):
    limite = _limite(solicitante_rn, rubrica_diarias, "1100")
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    solicitante_rn.notifications.all().delete()
    SpendingLimit.objects.filter(pk=limite.pk).update(valor_comprometido=Decimal("800"))

    check_budget_thresholds(limite_id=limite.pk)

    assert BudgetAlert.objects.get(escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk).faixa == "amarelo"
    assert set(solicitante_rn.notifications.values_list("tipo", flat=True)) == {TipoNotificacao.IN_APP}


@pytest.mark.django_db
def test_ajuste_em_linha_encerrada_resolve_o_alerta_sem_notificar(demand_request_rn, solicitante_rn):
    limite = SpendingLimitFactory(
        user=solicitante_rn, periodo_inicio=date(2020, 1, 1), periodo_fim=date(2020, 3, 31),
        valor_limite=Decimal("1000"), valor_comprometido=Decimal("950"),
    )
    alerta = BudgetAlert.objects.create(
        tipo=BudgetAlert.Tipo.SEMAFORO, escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk,
        faixa="vermelho", percentual_atingido=Decimal("95"),
    )

    balance_service._notificar_nova_faixa(
        limite, demand=demand_request_rn.demanda, rubrica_nome=limite.rubrica.nome, trava="individual",
    )

    alerta.refresh_from_db()
    assert alerta.resolvido_em is not None
    assert not solicitante_rn.notifications.exists()


@pytest.mark.django_db
def test_articulador_de_outro_estado_nao_e_avisado_por_ter_outro_perfil_no_estado(territory_rn):
    do_ce = TerritoryFactory(nome="Território CE", estados=["CE"])
    usuario = UserFactory(profiles=[
        (RoleFactory(slug="articulador-estadual"), do_ce), (RoleFactory(slug="adt-acr"), territory_rn),
    ])

    assert usuario not in notifications_service.usuarios_articuladores_do_estado("RN")
    assert usuario in notifications_service.usuarios_articuladores_do_estado("CE")


@pytest.mark.django_db
def test_recurso_extra_avisa_com_a_rubrica_e_o_saldo(solicitante_rn, rubrica_diarias, usuario_articulador_rn):
    _limite(solicitante_rn, rubrica_diarias, "1100")
    pedido = BudgetIncreaseRequestFactory(user=solicitante_rn, rubrica=rubrica_diarias, valor_solicitado=Decimal("50"))

    notifications_service.notificar_recurso_extra_submetido(pedido, [usuario_articulador_rn])

    notificacao = usuario_articulador_rn.notifications.get(tipo=TipoNotificacao.IN_APP)
    assert rubrica_diarias.nome in notificacao.titulo
    assert "1.100,00" in notificacao.mensagem


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


@pytest.mark.django_db
def test_remanejamento_em_estado_sem_articulador_avisa_a_ugp(
    activity_rn, rubrica_diarias, allocation_territorial_rn, usuario_ugp,
):
    origem = BudgetPoolFactory(
        rubrica=rubrica_diarias, nivel=BudgetPool.Nivel.ESTADUAL, territorio=None,
        estado=activity_rn.municipio.state, valor_alocado=Decimal("1500"),
    )

    remanejamento_service.remanejar_para_pool(
        origem=origem, destino=allocation_territorial_rn, valor=Decimal("100"), motivo="Excedente.",
        usuario=usuario_ugp, escopo=BudgetTransfer.Escopo.ELEVACAO_LIMITE,
    )

    assert _canais(usuario_ugp, "remanejamento_efetivado") == {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}
