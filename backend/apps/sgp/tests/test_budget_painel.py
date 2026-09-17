from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.sgp.models import BudgetAllocation, BudgetRubrica
from apps.sgp.tasks import check_budget_threshold_alert
from apps.sgp.tests.factories import (
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetAllocation.Nivel

PAINEL_URL = "/api/v1/sgp/orcamento/painel/"


def _linha(response, meta, rubrica):
    return next(
        linha for linha in response.data
        if linha["meta"]["id"] == meta.pk and linha["rubrica"]["id"] == rubrica.pk
    )


class TestPainelMatriz:
    def test_matriz_completa(self, auth_client_super_admin):
        for numero in range(1, 8):
            WorkPlanMetaFactory(numero=numero)

        response = auth_client_super_admin.get(PAINEL_URL)

        assert response.status_code == 200
        assert BudgetRubrica.objects.filter(ativo=True).count() == 6
        assert len(response.data) == 42


class TestPainelSemaforo:
    def test_semaforo_verde(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("5000"),
        )

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
        )

        linha = _linha(response, meta, rubrica)
        assert linha["semaforo"] == "verde"
        assert linha["alerta_80"] is False

    def test_semaforo_amarelo(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("7000"),
        )

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
        )

        linha = _linha(response, meta, rubrica)
        assert linha["semaforo"] == "amarelo"
        assert linha["alerta_80"] is False

    def test_semaforo_vermelho_em_80(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("8000"),
        )

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
        )

        linha = _linha(response, meta, rubrica)
        assert linha["semaforo"] == "vermelho"
        assert linha["alerta_80"] is True

    def test_alocacao_zerada_nao_quebra(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("0"), valor_comprometido=Decimal("0"),
        )

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
        )

        assert response.status_code == 200
        linha = _linha(response, meta, rubrica)
        assert linha["semaforo"] == "verde"
        assert Decimal(linha["valor_aprovado"]) == Decimal("0")


class TestPainelFiltros:
    def test_filtros(self, auth_client_super_admin, state_rn, territory_rn):
        meta = WorkPlanMetaFactory(numero=1)
        WorkPlanMetaFactory(numero=2)
        rubrica = BudgetRubricaFactory()
        BudgetRubricaFactory()  # outra rubrica, só pra garantir que o filtro restringe

        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("3000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn, valor_alocado=Decimal("1000"),
        )

        por_meta = auth_client_super_admin.get(f"{PAINEL_URL}?meta={meta.pk}")
        assert {linha["meta"]["id"] for linha in por_meta.data} == {meta.pk}

        por_rubrica = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}")
        assert {linha["rubrica"]["id"] for linha in por_rubrica.data} == {rubrica.pk}

        por_estado = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}&estado={state_rn.sigla}"
        )
        linha_estado = por_estado.data[0]
        assert linha_estado["nivel"] == "estadual"
        assert Decimal(linha_estado["valor_aprovado"]) == Decimal("3000")

        por_territorio = auth_client_super_admin.get(
            f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}&territorio={territory_rn.pk}"
        )
        linha_territorio = por_territorio.data[0]
        assert linha_territorio["nivel"] == "territorial"
        assert Decimal(linha_territorio["valor_aprovado"]) == Decimal("1000")

    def test_territorio_tem_precedencia_sobre_estado_quando_os_dois_vem(
        self, auth_client_super_admin, state_rn, territory_rn,
    ):
        WorkPlanMetaFactory()

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?estado={state_rn.sigla}&territorio={territory_rn.pk}"
        )

        assert response.status_code == 200
        assert len(response.data) > 0
        assert all(linha["nivel"] == "territorial" for linha in response.data)


class TestPainelEscopoTerritorial:
    def test_usuario_sem_perfil_no_sgp_recebe_403(self, auth_client_sem_acesso):
        response = auth_client_sem_acesso.get(PAINEL_URL)

        assert response.status_code == 403

    def test_escopo_territorial(
        self, auth_client_adt_rn, state_rn, territory_ce, territory_rn,
    ):
        outro_territorio = auth_client_adt_rn.get(f"{PAINEL_URL}?territorio={territory_ce.pk}")
        assert outro_territorio.status_code == 403

        proprio_territorio = auth_client_adt_rn.get(f"{PAINEL_URL}?territorio={territory_rn.pk}")
        assert proprio_territorio.status_code == 200

        sem_filtro = auth_client_adt_rn.get(PAINEL_URL)
        assert sem_filtro.status_code == 200

        sem_acesso_estadual = auth_client_adt_rn.get(f"{PAINEL_URL}?estado={state_rn.sigla}")
        assert sem_acesso_estadual.status_code == 403

        # `territorio` não resgata: ADT/ACR não tem nível estadual, mesmo mandando
        # o próprio território junto.
        estado_com_proprio_territorio = auth_client_adt_rn.get(
            f"{PAINEL_URL}?estado={state_rn.sigla}&territorio={territory_rn.pk}"
        )
        assert estado_com_proprio_territorio.status_code == 403

    def test_articulador_ve_nacional_por_padrao_e_pode_descer_no_proprio_estado(
        self, auth_client_articulador_rn, state_rn, state_ce, territory_rn, territory_ce,
    ):
        WorkPlanMetaFactory()

        sem_filtro = auth_client_articulador_rn.get(PAINEL_URL)
        assert sem_filtro.status_code == 200
        assert len(sem_filtro.data) > 0
        assert all(linha["nivel"] == "nacional" for linha in sem_filtro.data)

        proprio_estado = auth_client_articulador_rn.get(f"{PAINEL_URL}?estado={state_rn.sigla}")
        assert proprio_estado.status_code == 200
        assert len(proprio_estado.data) > 0
        assert all(linha["nivel"] == "estadual" for linha in proprio_estado.data)

        proprio_territorio = auth_client_articulador_rn.get(
            f"{PAINEL_URL}?territorio={territory_rn.pk}"
        )
        assert proprio_territorio.status_code == 200
        assert len(proprio_territorio.data) > 0
        assert all(linha["nivel"] == "territorial" for linha in proprio_territorio.data)

        outro_estado = auth_client_articulador_rn.get(f"{PAINEL_URL}?estado={state_ce.sigla}")
        assert outro_estado.status_code == 403

        outro_territorio = auth_client_articulador_rn.get(
            f"{PAINEL_URL}?territorio={territory_ce.pk}"
        )
        assert outro_territorio.status_code == 403

    def test_filtro_com_id_inexistente_e_400_pra_qualquer_perfil(
        self, auth_client_super_admin, auth_client_articulador_rn,
    ):
        response_global = auth_client_super_admin.get(f"{PAINEL_URL}?territorio=999999")
        assert response_global.status_code == 400

        response_escopado = auth_client_articulador_rn.get(f"{PAINEL_URL}?estado=XX")
        assert response_escopado.status_code == 400

        response_meta = auth_client_super_admin.get(f"{PAINEL_URL}?meta=999999")
        assert response_meta.status_code == 400

        response_rubrica = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica=nao-existe")
        assert response_rubrica.status_code == 400


class TestBudgetThresholdAlertTask:
    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_task_notifica_vermelhos(self, mocked_delay, usuario, usuario_super_admin):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("9000"),
        )

        total = check_budget_threshold_alert()

        assert total == 2
        assert mocked_delay.call_count == 2
        notifications = usuario.notifications.filter(evento="budget_allocation_red")
        assert notifications.count() == 1
        assert meta.titulo in notifications.first().titulo

    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_task_notifica_vermelhos_em_qualquer_nivel(
        self, mocked_delay, usuario, usuario_super_admin, state_rn, territory_rn,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("9000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1000"), valor_comprometido=Decimal("100"),
        )

        total = check_budget_threshold_alert()

        assert total == 2
        notifications = usuario.notifications.filter(evento="budget_allocation_red")
        assert notifications.count() == 1

    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_does_not_notify_when_nothing_is_red(self, mocked_delay, usuario):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("5000"),
        )

        assert check_budget_threshold_alert() == 0
        assert mocked_delay.call_count == 0

    def test_schedule_runs_daily(self, settings):
        schedule = settings.CELERY_BEAT_SCHEDULE["check_budget_threshold_alert"]

        assert schedule["task"] == "sgp.tasks.check_budget_threshold_alert"


class TestPainelPerformance:
    def test_numero_de_queries(
        self, auth_client_super_admin, django_assert_num_queries, state_rn, territory_rn,
    ):
        rubricas = list(BudgetRubrica.objects.filter(ativo=True))
        for numero in range(1, 8):
            meta = WorkPlanMetaFactory(numero=numero)
            for rubrica in rubricas:
                BudgetAllocationFactory(
                    meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
                    estado=None, territorio=None, valor_alocado=Decimal("1000"),
                )
                BudgetAllocationFactory(
                    meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
                    estado=state_rn, territorio=None, valor_alocado=Decimal("500"),
                )
                BudgetAllocationFactory(
                    meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
                    estado=None, territorio=territory_rn, valor_alocado=Decimal("200"),
                )

        with django_assert_num_queries(5):
            response = auth_client_super_admin.get(PAINEL_URL)

        assert response.status_code == 200
        assert len(response.data) == 42

    def test_numero_de_queries_adt_sem_filtro(
        self, auth_client_adt_rn, django_assert_num_queries,
    ):
        # ADT/ACR tem nível padrão territorial (folha, sem "distribuído") — 1 query a
        # menos que o caminho nacional/estadual dos outros perfis.
        WorkPlanMetaFactory()

        with django_assert_num_queries(4):
            response = auth_client_adt_rn.get(PAINEL_URL)

        assert response.status_code == 200

    def test_numero_de_queries_com_filtros(
        self, auth_client_super_admin, django_assert_num_queries, state_rn, territory_rn,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn, valor_alocado=Decimal("200"),
        )

        with django_assert_num_queries(8):
            response = auth_client_super_admin.get(
                f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}&estado={state_rn.sigla}"
            )

        assert response.status_code == 200

    def test_numero_de_queries_com_filtros_articulador(
        self, auth_client_articulador_rn, django_assert_num_queries, state_rn, territory_rn,
    ):
        # Articulador Estadual paga +1 query em resolver_nivel_painel (confirma posse
        # do território) sobre o caminho de super-admin/ugp — pior caso real, 9.
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetAllocationFactory(
            meta=meta, rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn, valor_alocado=Decimal("200"),
        )

        with django_assert_num_queries(9):
            response = auth_client_articulador_rn.get(
                f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
                f"&estado={state_rn.sigla}&territorio={territory_rn.pk}"
            )

        assert response.status_code == 200
