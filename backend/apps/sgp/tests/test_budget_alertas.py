"""Alertas orçamentários: semáforo, subexecução, remanejamento excessivo e reconciliação."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from freezegun import freeze_time

from apps.core.models.notifications import Notification, TipoNotificacao
from apps.core.models.system_config import SystemConfig
from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.budget import alertas
from apps.sgp.budget import services as budget_service
from apps.sgp.models import BudgetAlert, BudgetPool, BudgetRubrica, BudgetTransaction, SpendingLimit
from apps.sgp.signals.budget import avaliar_alertas_da_movimentacao
from apps.sgp.tasks import (
    check_budget_threshold_alert,
    check_budget_thresholds,
    check_budget_underexecution,
    reconcile_budget_balances,
)
from apps.sgp.tests.factories import (
    BudgetPoolFactory,
    BudgetRubricaFactory,
    SpendingLimitFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel
Tipo = BudgetAlert.Tipo
URL = "/api/v1/sgp/orcamento/alertas/"
EMAIL_E_IN_APP = {TipoNotificacao.EMAIL, TipoNotificacao.IN_APP}


PARAMETROS = ("budget_subexec_alert_months", "budget_subexec_min_pct", "budget_transfer_alert_pct")


@pytest.fixture(autouse=True)
def sem_envio_de_email():
    with patch("apps.core.tasks.notifications.send_email_notification.delay"):
        yield


@pytest.fixture(autouse=True)
def parametros_sem_cache():
    """O cache de `get_config` não volta com o rollback do teste."""
    cache.delete_many([f"system_config:{chave}" for chave in PARAMETROS])
    yield
    cache.delete_many([f"system_config:{chave}" for chave in PARAMETROS])


def _config(chave, valor):
    SystemConfig.objects.update_or_create(chave=chave, defaults={"valor": str(valor), "tipo": "integer"})
    cache.delete(f"system_config:{chave}")


def _territorial(territorio, *, comprometido, alocado=1000, **campos):
    return BudgetPoolFactory(
        nivel=Nivel.TERRITORIAL, estado=None, territorio=territorio, valor_alocado=Decimal(alocado),
        valor_comprometido=Decimal(comprometido), **campos,
    )


def _nacional(rubrica=None, *, alocado=1000, executado=0):
    return BudgetPoolFactory(
        rubrica=rubrica or BudgetRubricaFactory(), nivel=Nivel.NACIONAL, estado=None, territorio=None,
        valor_alocado=Decimal(alocado), valor_executado=Decimal(executado),
    )


def _mudar(pool, comprometido):
    BudgetPool.objects.filter(pk=pool.pk).update(valor_comprometido=Decimal(comprometido))


def _avaliar(pool):
    return check_budget_thresholds(pool_id=pool.pk)


def _canais(usuario, evento=alertas.EVENTO_SEMAFORO):
    return set(usuario.notifications.filter(evento=evento).values_list("tipo", flat=True))


# ---------- Modelo ----------

class TestAlertaAberto:
    def _alerta(self, **campos):
        return BudgetAlert.objects.create(
            tipo=Tipo.SEMAFORO, escopo=BudgetAlert.Escopo.POOL, referencia_id=1, percentual_atingido=Decimal("75"),
            **campos,
        )

    def test_nao_aceita_dois_abertos_para_o_mesmo_alvo_e_tipo(self):
        self._alerta()

        with pytest.raises(IntegrityError), transaction.atomic():
            self._alerta()

    def test_aceita_novo_depois_de_resolvido(self):
        alerta = self._alerta()
        alerta.resolvido_em = alerta.alertado_em
        alerta.save(update_fields=["resolvido_em"])

        self._alerta()

        assert BudgetAlert.objects.count() == 2


# ---------- Semáforo ----------

class TestSemaforo:
    def test_verde_nao_abre_alerta(self, territory_rn):
        _avaliar(_territorial(territory_rn, comprometido=100))

        assert not BudgetAlert.objects.exists()
        assert not Notification.objects.exists()

    def test_amarelo_avisa_o_responsavel_so_no_app(self, territory_rn, usuario_articulador_rn, usuario):
        pool = _territorial(territory_rn, comprometido=750)

        _avaliar(pool)

        alerta = BudgetAlert.objects.get()
        assert (alerta.tipo, alerta.escopo, alerta.referencia_id, alerta.rubrica_id, alerta.faixa) == (
            Tipo.SEMAFORO, BudgetAlert.Escopo.POOL, pool.pk, pool.rubrica_id, "amarelo",
        )
        assert alerta.percentual_atingido == Decimal("75.00")
        assert alerta.usuarios_alertados_ids == [usuario_articulador_rn.pk]
        assert _canais(usuario_articulador_rn) == {TipoNotificacao.IN_APP}
        assert not usuario.notifications.exists()

    def test_vermelho_avisa_tambem_o_nivel_superior_por_email(self, territory_rn, usuario_articulador_rn, usuario):
        _avaliar(_territorial(territory_rn, comprometido=950))

        assert _canais(usuario_articulador_rn) == EMAIL_E_IN_APP
        assert _canais(usuario) == EMAIL_E_IN_APP

    def test_mensagem_traz_o_local_a_rubrica_e_o_saldo(self, territory_rn, usuario_articulador_rn):
        pool = _territorial(territory_rn, comprometido=950)

        _avaliar(pool)

        notificacao = usuario_articulador_rn.notifications.first()
        assert pool.rubrica.nome in notificacao.titulo
        assert territory_rn.nome in notificacao.mensagem
        assert "50,00" in notificacao.mensagem

    def test_rodar_duas_vezes_nao_duplica_alerta_nem_notificacao(self, territory_rn, usuario_articulador_rn):
        pool = _territorial(territory_rn, comprometido=950)

        _avaliar(pool)
        total = usuario_articulador_rn.notifications.count()
        assert _avaliar(pool) == 0

        assert BudgetAlert.objects.count() == 1
        assert usuario_articulador_rn.notifications.count() == total

    def test_ciclo_de_faixas(self, territory_rn, usuario_articulador_rn):
        pool = _territorial(territory_rn, comprometido=750)
        _avaliar(pool)

        _mudar(pool, 950)
        assert _avaliar(pool) > 0
        assert BudgetAlert.objects.get().faixa == "vermelho"

        _mudar(pool, 750)
        assert _avaliar(pool) > 0
        assert BudgetAlert.objects.get().faixa == "amarelo"

        _mudar(pool, 100)
        assert _avaliar(pool) == 0
        assert BudgetAlert.objects.get().resolvido_em is not None

        _mudar(pool, 750)
        assert _avaliar(pool) > 0
        assert BudgetAlert.objects.count() == 2

    @pytest.mark.parametrize("nivel,responsavel,superior", [
        (Nivel.ESTADUAL, "articulador", "ugp"),
        (Nivel.NACIONAL, "ugp", "super_admin"),
    ])
    def test_vermelho_em_cada_nivel_vai_ao_responsavel_e_ao_superior(
        self, nivel, responsavel, superior, state_rn, usuario, usuario_super_admin, usuario_articulador_rn,
    ):
        pessoas = {"ugp": usuario, "super_admin": usuario_super_admin, "articulador": usuario_articulador_rn}
        pool = BudgetPoolFactory(
            nivel=nivel, estado=state_rn if nivel == Nivel.ESTADUAL else None, territorio=None,
            valor_alocado=Decimal("1000"), valor_comprometido=Decimal("950"),
        )

        _avaliar(pool)

        assert set(BudgetAlert.objects.get().usuarios_alertados_ids) == {
            pessoas[responsavel].pk, pessoas[superior].pk,
        }
        assert _canais(pessoas[responsavel]) == _canais(pessoas[superior]) == EMAIL_E_IN_APP

    def test_amarelo_no_nacional_avisa_so_a_ugp(self, usuario, usuario_super_admin):
        pool = _nacional(alocado=1000)
        _mudar(pool, 750)

        _avaliar(pool)

        assert _canais(usuario) == {TipoNotificacao.IN_APP}
        assert not usuario_super_admin.notifications.exists()

    def test_vermelho_no_limite_do_articulador_vai_a_ugp(self, usuario_articulador_rn, usuario):
        limite = SpendingLimitFactory(user=usuario_articulador_rn, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario_articulador_rn) == EMAIL_E_IN_APP
        assert _canais(usuario) == EMAIL_E_IN_APP

    def test_vermelho_no_limite_do_super_admin_avisa_ele_uma_vez_por_canal(self, usuario_super_admin):
        limite = SpendingLimitFactory(user=usuario_super_admin, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert usuario_super_admin.notifications.count() == len(EMAIL_E_IN_APP)

    def test_vermelho_no_limite_da_fgd_vai_a_ugp(self, usuario_fgd, usuario):
        limite = SpendingLimitFactory(user=usuario_fgd, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario) == EMAIL_E_IN_APP

    def test_vermelho_no_limite_de_usuario_sem_perfil_vai_a_ugp(self, usuario):
        limite = SpendingLimitFactory(user=UserFactory(), valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario) == EMAIL_E_IN_APP

    def test_limite_avisa_o_articulador_do_territorio_da_linha(
        self, usuario_adt_rn, usuario_articulador_rn, territory_rn, territory_ce,
    ):
        do_ce = UserFactory(profiles=[(usuario_articulador_rn.profiles.get().perfil, territory_ce)])
        tecnico = UserFactory(profiles=[
            (usuario_adt_rn.profiles.get().perfil, territory_rn), (usuario_adt_rn.profiles.get().perfil, territory_ce),
        ])
        limite = SpendingLimitFactory(user=tecnico, territorio=territory_rn, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario_articulador_rn) == EMAIL_E_IN_APP
        assert not do_ce.notifications.exists()

    def test_amarelo_em_estado_sem_articulador_avisa_a_ugp(self, state_rn, usuario):
        pool = BudgetPoolFactory(
            nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
            valor_comprometido=Decimal("750"),
        )

        _avaliar(pool)

        assert _canais(usuario) == {TipoNotificacao.IN_APP}

    def test_vermelho_no_limite_da_ugp_vai_ao_super_admin(self, usuario, usuario_super_admin):
        limite = SpendingLimitFactory(user=usuario, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario_super_admin) == EMAIL_E_IN_APP

    def test_limite_sem_articulador_no_estado_sobe_para_a_ugp(self, usuario_adt_rn, usuario):
        limite = SpendingLimitFactory(user=usuario_adt_rn, valor_limite=1000, valor_comprometido=950)

        check_budget_thresholds(limite_id=limite.pk)

        assert _canais(usuario) == EMAIL_E_IN_APP

    def test_periodo_encerrado_resolve_o_alerta_e_nao_notifica(self, usuario_adt_rn):
        limite = SpendingLimitFactory(
            user=usuario_adt_rn, periodo_inicio=date(2020, 1, 1), periodo_fim=date(2020, 3, 31),
            valor_limite=1000, valor_comprometido=950,
        )
        aberto = BudgetAlert.objects.create(
            tipo=Tipo.SEMAFORO, escopo=BudgetAlert.Escopo.LIMITE, referencia_id=limite.pk,
            faixa="vermelho", percentual_atingido=Decimal("95"),
        )

        assert check_budget_thresholds(limite_id=limite.pk) == 0

        aberto.refresh_from_db()
        assert aberto.resolvido_em is not None
        assert not BudgetAlert.objects.filter(resolvido_em__isnull=True).exists()
        assert not usuario_adt_rn.notifications.exists()

    def test_limite_de_outro_periodo_nao_abre_alerta(self, usuario_adt_rn):
        limite = SpendingLimitFactory(
            user=usuario_adt_rn, periodo_inicio=date(2020, 1, 1), periodo_fim=date(2020, 3, 31),
            valor_limite=1000, valor_comprometido=950,
        )

        check_budget_thresholds(limite_id=limite.pk)

        assert not BudgetAlert.objects.exists()

    def test_limite_avisa_o_usuario_e_no_vermelho_o_articulador(self, usuario_adt_rn, usuario_articulador_rn):
        limite = SpendingLimitFactory(user=usuario_adt_rn, valor_limite=1000, valor_comprometido=750)

        check_budget_thresholds(limite_id=limite.pk)
        assert _canais(usuario_adt_rn) == {TipoNotificacao.IN_APP}
        assert not usuario_articulador_rn.notifications.exists()

        SpendingLimit.objects.filter(pk=limite.pk).update(valor_comprometido=950)
        check_budget_thresholds(limite_id=limite.pk)
        assert _canais(usuario_adt_rn) == EMAIL_E_IN_APP
        assert _canais(usuario_articulador_rn) == EMAIL_E_IN_APP
        assert BudgetAlert.objects.get().escopo == BudgetAlert.Escopo.LIMITE

    def test_percentual_enorme_cabe_no_campo(self, usuario_adt_rn):
        limite = SpendingLimitFactory(user=usuario_adt_rn, valor_limite=Decimal("0.01"), valor_comprometido=999999)

        check_budget_thresholds(limite_id=limite.pk)

        assert BudgetAlert.objects.get().percentual_atingido == Decimal("999999.99")

    def test_rodada_completa_cobre_pools_e_limites_e_resolve_periodo_encerrado(self, territory_rn, usuario_adt_rn):
        pool = _territorial(territory_rn, comprometido=950)
        vigente = SpendingLimitFactory(user=usuario_adt_rn, valor_limite=1000, valor_comprometido=950)
        encerrado = SpendingLimitFactory(
            user=usuario_adt_rn, periodo_inicio=date(2020, 1, 1), periodo_fim=date(2020, 3, 31),
            valor_limite=1000, valor_comprometido=950,
        )
        antigo = BudgetAlert.objects.create(
            tipo=Tipo.SEMAFORO, escopo=BudgetAlert.Escopo.LIMITE, referencia_id=encerrado.pk,
            faixa="vermelho", percentual_atingido=Decimal("95"),
        )

        check_budget_thresholds()

        abertos = BudgetAlert.objects.filter(resolvido_em__isnull=True).values_list("escopo", "referencia_id")
        assert set(abertos) == {(BudgetAlert.Escopo.POOL, pool.pk), (BudgetAlert.Escopo.LIMITE, vigente.pk)}
        antigo.refresh_from_db()
        assert antigo.resolvido_em is not None

    def test_movimentacao_agenda_a_avaliacao_do_alvo(self, django_capture_on_commit_callbacks):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))

        with patch("apps.sgp.tasks.check_budget_thresholds.delay") as delay:
            with django_capture_on_commit_callbacks(execute=True):
                budget_service.reservar(pool=pool, valor=Decimal("100"), demand_request_id="s1", usuario=UserFactory())

        delay.assert_called_once_with(pool_id=pool.pk, limite_id=None)

    def test_carga_de_fixture_nao_agenda(self):
        with patch("apps.sgp.signals.budget.transaction.on_commit") as on_commit:
            avaliar_alertas_da_movimentacao(BudgetTransaction, instance=BudgetTransaction(), created=True, raw=True)

        on_commit.assert_not_called()

    def test_mesmo_alvo_na_mesma_transacao_agenda_uma_vez(self, django_capture_on_commit_callbacks):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        with patch("apps.sgp.tasks.check_budget_thresholds.delay") as delay:
            with django_capture_on_commit_callbacks(execute=True):
                budget_service.reservar(pool=pool, valor=Decimal("100"), demand_request_id="s1", usuario=usuario)
                budget_service.reservar(pool=pool, valor=Decimal("100"), demand_request_id="s2", usuario=usuario)

        delay.assert_called_once_with(pool_id=pool.pk, limite_id=None)

    def test_savepoint_desfeito_nao_impede_o_agendamento_seguinte(self, django_capture_on_commit_callbacks):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        with patch("apps.sgp.tasks.check_budget_thresholds.delay") as delay:
            with django_capture_on_commit_callbacks(execute=True):
                with pytest.raises(ValueError), transaction.atomic():
                    budget_service.reservar(pool=pool, valor=Decimal("100"), demand_request_id="s1", usuario=usuario)
                    raise ValueError
                budget_service.reservar(pool=pool, valor=Decimal("100"), demand_request_id="s2", usuario=usuario)

        delay.assert_called_once_with(pool_id=pool.pk, limite_id=None)

    def test_nome_antigo_da_tarefa_ainda_funciona(self, territory_rn):
        _territorial(territory_rn, comprometido=950)

        check_budget_threshold_alert()

        assert BudgetAlert.objects.filter(tipo=Tipo.SEMAFORO).exists()

    def test_agendamentos(self, settings):
        agenda = settings.CELERY_BEAT_SCHEDULE

        assert "check_budget_threshold_alert" not in agenda
        assert agenda["check_budget_thresholds"]["task"] == "sgp.tasks.check_budget_thresholds"
        assert agenda["check_budget_underexecution"]["task"] == "sgp.tasks.check_budget_underexecution"
        assert agenda["reconcile_budget_balances"]["task"] == "sgp.tasks.reconcile_budget_balances"
        assert (agenda["reconcile_budget_balances"]["schedule"].hour, agenda["reconcile_budget_balances"]["schedule"].minute) == ({2}, {30})
        assert agenda["check_budget_underexecution"]["schedule"].day_of_week == {1}

    def test_remover_pool_apaga_os_alertas_dele(self, territory_rn):
        pool = _territorial(territory_rn, comprometido=0)
        BudgetAlert.objects.create(
            tipo=Tipo.SEMAFORO, escopo=BudgetAlert.Escopo.POOL, referencia_id=pool.pk,
            faixa="amarelo", percentual_atingido=Decimal("75"),
        )

        budget_service.remover_pool(pool)

        assert not BudgetAlert.objects.exists()


# ---------- Subexecução ----------

class TestSubexecucao:
    @pytest.fixture
    def rubrica_nacional(self):
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31))
        return _nacional(alocado=1000, executado=100)

    @pytest.mark.parametrize("hoje,abre", [("2026-06-29 12:00", False), ("2026-06-30 12:00", True), ("2026-07-01 12:00", True)])
    def test_abre_a_partir_de_seis_meses_do_fim(self, rubrica_nacional, usuario, hoje, abre):
        with freeze_time(hoje):
            check_budget_underexecution()

        assert BudgetAlert.objects.filter(tipo=Tipo.SUBEXECUCAO, faixa="subexecucao").exists() is abre
        assert bool(_canais(usuario, alertas.EVENTO_SUBEXECUCAO)) is abre

    @freeze_time("2026-02-28 12:00")
    def test_fronteira_em_mes_mais_curto(self, usuario):
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2026, 8, 31))
        _nacional(alocado=1000)

        check_budget_underexecution()

        assert BudgetAlert.objects.filter(tipo=Tipo.SUBEXECUCAO).exists()

    @freeze_time("2026-10-01 12:00")
    def test_vigencia_e_a_maior_data_fim_das_metas(self, usuario):
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31))
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2028, 12, 31))
        _nacional(alocado=1000)

        check_budget_underexecution()

        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-10-01 12:00")
    def test_soma_a_execucao_de_todos_os_niveis(self, rubrica_nacional, usuario, territory_rn):
        _territorial(territory_rn, comprometido=0, rubrica=rubrica_nacional.rubrica, valor_executado=Decimal("500"))

        check_budget_underexecution()

        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-10-01 12:00")
    def test_rodar_duas_vezes_nao_duplica_e_resolve_quando_executa(self, rubrica_nacional, usuario):
        check_budget_underexecution()
        total = usuario.notifications.count()
        assert check_budget_underexecution() == 0
        assert usuario.notifications.count() == total
        assert BudgetAlert.objects.count() == 1

        BudgetPool.objects.filter(pk=rubrica_nacional.pk).update(valor_executado=Decimal("600"))
        check_budget_underexecution()

        assert BudgetAlert.objects.get().resolvido_em is not None

    @freeze_time("2026-10-01 12:00")
    def test_parametros_vem_do_core(self, rubrica_nacional, usuario):
        _config("budget_subexec_min_pct", 5)

        check_budget_underexecution()
        assert not BudgetAlert.objects.exists()

        _config("budget_subexec_min_pct", 60)
        _config("budget_subexec_alert_months", 1)
        check_budget_underexecution()
        assert not BudgetAlert.objects.exists()

    @freeze_time("2026-10-01 12:00")
    def test_base_e_o_valor_aprovado_nao_o_que_sobrou_no_nacional(self, usuario, state_rn):
        WorkPlanMetaFactory(data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31))
        nacional = _nacional(alocado=1000, executado=300)
        destino = BudgetPoolFactory(
            rubrica=nacional.rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("0"),
        )
        budget_service.remanejar_com_registro(
            origem=nacional, destino=destino, valor=Decimal("500"), usuario=usuario, justificativa="Teste.",
        )

        check_budget_underexecution()

        assert BudgetAlert.objects.get(tipo=Tipo.SUBEXECUCAO).percentual_atingido == Decimal("30.00")

    @freeze_time("2026-10-01 12:00")
    def test_alerta_de_rubrica_inativada_e_resolvido(self, rubrica_nacional, usuario):
        check_budget_underexecution()
        assert BudgetAlert.objects.get(tipo=Tipo.SUBEXECUCAO).resolvido_em is None

        BudgetRubrica.objects.filter(pk=rubrica_nacional.rubrica_id).update(ativo=False)
        check_budget_underexecution()

        assert BudgetAlert.objects.get(tipo=Tipo.SUBEXECUCAO).resolvido_em is not None

    def test_sem_metas_nao_ha_alerta(self, usuario):
        _nacional(alocado=1000)

        assert check_budget_underexecution() == 0
        assert not BudgetAlert.objects.exists()


# ---------- Remanejamento ----------

class TestRemanejamento:
    @pytest.fixture
    def pools(self, state_rn, state_ce):
        rubrica = BudgetRubricaFactory()
        nacional = _nacional(rubrica, alocado=1000)
        origem = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("500"),
        )
        destino = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None, valor_alocado=Decimal("100"),
        )
        return nacional, origem, destino

    def _remanejar(self, origem, destino, valor, usuario):
        budget_service.remanejar_com_registro(
            origem=origem, destino=destino, valor=Decimal(valor), usuario=usuario, justificativa="Teste.",
        )

    def test_acima_do_percentual_alerta_a_ugp_uma_vez(self, pools, usuario):
        nacional, origem, destino = pools
        self._remanejar(origem, destino, "300", usuario)

        check_budget_thresholds()
        total = usuario.notifications.filter(evento=alertas.EVENTO_REMANEJAMENTO_EXCESSIVO).count()
        check_budget_thresholds()

        alerta = BudgetAlert.objects.get(tipo=Tipo.REMANEJAMENTO_EXCESSIVO)
        assert (alerta.referencia_id, alerta.rubrica_id, alerta.faixa) == (nacional.pk, nacional.rubrica_id, "")
        assert alerta.percentual_atingido == Decimal("30.00")
        assert total == 2
        assert usuario.notifications.filter(evento=alertas.EVENTO_REMANEJAMENTO_EXCESSIVO).count() == 2

    def test_abaixo_do_percentual_nao_alerta(self, pools, usuario):
        _, origem, destino = pools
        self._remanejar(origem, destino, "200", usuario)

        check_budget_thresholds()

        assert not BudgetAlert.objects.filter(tipo=Tipo.REMANEJAMENTO_EXCESSIVO).exists()

    def test_percentual_vem_do_core(self, pools, usuario):
        _, origem, destino = pools
        _config("budget_transfer_alert_pct", 10)
        self._remanejar(origem, destino, "200", usuario)

        check_budget_thresholds()

        assert BudgetAlert.objects.filter(tipo=Tipo.REMANEJAMENTO_EXCESSIVO).exists()

    def test_base_desfaz_o_que_saiu_do_pool_nacional(self, pools, usuario):
        nacional, _, destino = pools
        # 220/1000 fica abaixo de 25%; sem desfazer o que saiu, seria 220/780.
        self._remanejar(nacional, destino, "220", usuario)

        check_budget_thresholds()

        assert not BudgetAlert.objects.filter(tipo=Tipo.REMANEJAMENTO_EXCESSIVO).exists()

    def test_alerta_de_rubrica_inativada_e_resolvido(self, pools, usuario):
        nacional, origem, destino = pools
        self._remanejar(origem, destino, "300", usuario)
        check_budget_thresholds()
        assert BudgetAlert.objects.get(tipo=Tipo.REMANEJAMENTO_EXCESSIVO).resolvido_em is None

        BudgetRubrica.objects.filter(pk=nacional.rubrica_id).update(ativo=False)
        check_budget_thresholds()

        assert BudgetAlert.objects.get(tipo=Tipo.REMANEJAMENTO_EXCESSIVO).resolvido_em is not None

    def test_efetivado_avisa_os_responsaveis_de_origem_e_destino_com_o_saldo_depois(
        self, pools, usuario, usuario_articulador_rn, territory_ce,
    ):
        _, origem, destino = pools
        papel = usuario_articulador_rn.profiles.get().perfil
        articulador_ce = UserFactory(profiles=[(papel, territory_ce)])

        self._remanejar(origem, destino, "100", usuario)

        for articulador in (usuario_articulador_rn, articulador_ce):
            assert _canais(articulador, alertas.EVENTO_REMANEJAMENTO_EFETIVADO) == EMAIL_E_IN_APP
        assert "400,00" in usuario_articulador_rn.notifications.first().mensagem


# ---------- Reconciliação ----------

class TestReconciliacao:
    def test_sem_divergencia_nao_notifica(self, usuario_super_admin):
        assert reconcile_budget_balances() == 0
        assert not usuario_super_admin.notifications.exists()

    def test_divergencia_notifica_o_super_admin(self, usuario_super_admin, territory_rn):
        pool = _territorial(territory_rn, comprometido=0)
        BudgetPool.objects.filter(pk=pool.pk).update(valor_comprometido=Decimal("10"))

        assert reconcile_budget_balances() >= 1
        assert _canais(usuario_super_admin, alertas.EVENTO_RECONCILIACAO) == EMAIL_E_IN_APP
        assert f"Pool #{pool.pk}" in usuario_super_admin.notifications.first().mensagem


# ---------- Listagem ----------

class TestListagem:
    @pytest.fixture
    def cenario(self, territory_rn, territory_ce, usuario_adt_rn):
        do_rn = _territorial(territory_rn, comprometido=950)
        do_ce = _territorial(territory_ce, comprometido=950)
        meu_limite = SpendingLimitFactory(
            user=usuario_adt_rn, territorio=territory_rn, valor_limite=1000, valor_comprometido=950,
        )
        outro_limite = SpendingLimitFactory(valor_limite=1000, valor_comprometido=950)
        nacional = _nacional()
        for pool in (do_rn, do_ce):
            check_budget_thresholds(pool_id=pool.pk)
        for limite in (meu_limite, outro_limite):
            check_budget_thresholds(limite_id=limite.pk)
        BudgetAlert.objects.create(
            tipo=Tipo.SUBEXECUCAO, escopo=BudgetAlert.Escopo.POOL, referencia_id=nacional.pk,
            rubrica=nacional.rubrica, faixa="subexecucao", percentual_atingido=Decimal("10"),
        )
        return {"rn": do_rn, "ce": do_ce, "meu": meu_limite, "outro": outro_limite, "nacional": nacional}

    def _alvos(self, cliente, **filtros):
        resposta = cliente.get(URL, filtros)
        assert resposta.status_code == 200
        return {(item["escopo"], item["referencia_id"]) for item in resposta.json()["results"]}

    def test_super_admin_ve_todos(self, auth_client_super_admin, cenario):
        assert len(self._alvos(auth_client_super_admin)) == 5

    def test_ugp_ve_todos(self, auth_client, cenario):
        assert len(self._alvos(auth_client)) == 5

    def test_fgd_ve_os_pools_e_so_o_proprio_limite(self, auth_client_fgd, usuario_fgd, cenario):
        proprio = SpendingLimitFactory(user=usuario_fgd, valor_limite=1000, valor_comprometido=950)
        check_budget_thresholds(limite_id=proprio.pk)

        assert self._alvos(auth_client_fgd) == {
            (BudgetAlert.Escopo.POOL, cenario["rn"].pk),
            (BudgetAlert.Escopo.POOL, cenario["ce"].pk),
            (BudgetAlert.Escopo.POOL, cenario["nacional"].pk),
            (BudgetAlert.Escopo.LIMITE, proprio.pk),
        }

    def test_articulador_sem_territorio_ve_pools_e_limites_de_todos_os_estados(self, api_client, cenario):
        papel = RoleFactory(slug="articulador-estadual")
        api_client.force_authenticate(user=UserFactory(profiles=[(papel, None)]))

        alvos = self._alvos(api_client)

        assert {(BudgetAlert.Escopo.POOL, cenario["rn"].pk), (BudgetAlert.Escopo.POOL, cenario["ce"].pk)} <= alvos
        assert (BudgetAlert.Escopo.POOL, cenario["nacional"].pk) not in alvos
        assert (BudgetAlert.Escopo.LIMITE, cenario["meu"].pk) in alvos
        assert (BudgetAlert.Escopo.LIMITE, cenario["outro"].pk) not in alvos

    def test_adt_com_dois_perfis_ve_os_dois_territorios(self, api_client, usuario_adt_rn, territory_rn, territory_ce, cenario):
        papel = usuario_adt_rn.profiles.get().perfil
        api_client.force_authenticate(user=UserFactory(profiles=[(papel, territory_rn), (papel, territory_ce)]))

        assert self._alvos(api_client) == {
            (BudgetAlert.Escopo.POOL, cenario["rn"].pk), (BudgetAlert.Escopo.POOL, cenario["ce"].pk),
        }

    def test_nao_expoe_quem_foi_alertado(self, auth_client_adt_rn, cenario):
        for item in auth_client_adt_rn.get(URL).json()["results"]:
            assert "usuarios_alertados_ids" not in item

    def test_articulador_ve_o_proprio_estado(self, auth_client_articulador_rn, cenario):
        assert self._alvos(auth_client_articulador_rn) == {
            (BudgetAlert.Escopo.POOL, cenario["rn"].pk), (BudgetAlert.Escopo.LIMITE, cenario["meu"].pk),
        }

    def test_adt_ve_o_pool_do_territorio_e_o_proprio_limite(self, auth_client_adt_rn, cenario):
        assert self._alvos(auth_client_adt_rn) == {
            (BudgetAlert.Escopo.POOL, cenario["rn"].pk), (BudgetAlert.Escopo.LIMITE, cenario["meu"].pk),
        }

    def test_sem_acesso_ao_orcamento_recebe_403(self, auth_client_sem_acesso):
        assert auth_client_sem_acesso.get(URL).status_code == 403

    def test_filtros(self, auth_client_super_admin, cenario):
        nacional = (BudgetAlert.Escopo.POOL, cenario["nacional"].pk)

        assert self._alvos(auth_client_super_admin, tipo="subexecucao") == {nacional}
        assert self._alvos(auth_client_super_admin, faixa="subexecucao") == {nacional}
        BudgetAlert.objects.filter(tipo=Tipo.SUBEXECUCAO).update(resolvido_em=timezone.now())
        assert nacional not in self._alvos(auth_client_super_admin, abertos="true")
        assert self._alvos(auth_client_super_admin, abertos="false") == {nacional}

    def test_filtro_invalido_responde_400(self, auth_client_super_admin):
        assert auth_client_super_admin.get(URL, {"tipo": "outro"}).status_code == 400


# ---------- Catálogo de eventos

@pytest.mark.parametrize("modelo", sorted(alertas.MODELOS))
def test_todo_evento_traz_a_rubrica_e_o_saldo_disponivel(modelo):
    titulo, mensagem = alertas.MODELOS[modelo]

    assert "{{rubrica}}" in titulo + mensagem
    assert "{{saldo_disponivel}}" in mensagem


def test_renderizar_preenche_as_variaveis():
    titulo, mensagem = alertas.renderizar(
        "semaforo", rubrica="Diárias", faixa="amarelo", trava="individual", saldo_disponivel="R$ 10,00",
    )

    assert titulo == "Saldo de Diárias entrou na faixa amarelo"
    assert "R$ 10,00" in mensagem
    assert "{{" not in titulo + mensagem
