from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.tests.factories import UserFactory
from apps.sgp.budget import services as budget_service
from apps.sgp.models import BudgetPool, BudgetRubrica
from apps.sgp.tasks import check_budget_threshold_alert
from apps.sgp.tests.factories import (
    ActivityFactory,
    BudgetPoolFactory,
    BudgetRubricaFactory,
    WorkPlanAcaoFactory,
    WorkPlanMetaFactory,
)

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel

PAINEL_URL = "/api/v1/sgp/orcamento/painel/"


def _pool_nacional(rubrica=None, **valores):
    return BudgetPoolFactory(
        rubrica=rubrica or BudgetRubricaFactory(), nivel=Nivel.NACIONAL, estado=None, territorio=None, **valores,
    )


def _linha(response, pool):
    return next(linha for linha in response.data if linha["id"] == pool.pk)


class TestMatrizRubricaPorNivel:
    def test_uma_linha_por_pool_com_id_nivel_e_localizacao(
        self, auth_client_super_admin, state_rn, territory_rn,
    ):
        rubrica = BudgetRubricaFactory()
        nacional = _pool_nacional(rubrica, valor_alocado=Decimal("10000"))
        estadual = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("4000"),
        )
        territorial = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1000"),
        )

        response = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}")

        assert response.status_code == 200
        assert [linha["id"] for linha in response.data] == [nacional.pk, estadual.pk, territorial.pk]
        assert "meta" not in response.data[0]
        assert _linha(response, nacional)["estado"] is None
        assert _linha(response, nacional)["territorio"] is None
        assert _linha(response, estadual)["estado"]["sigla"] == state_rn.sigla
        assert _linha(response, territorial)["territorio"]["id"] == territory_rn.pk

    def test_distribuido_e_saldos_por_nivel(self, auth_client_super_admin, state_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        nacional = _pool_nacional(rubrica, valor_alocado=Decimal("10000"), valor_comprometido=Decimal("1000"))
        estadual = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("4000"),
        )
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1500"),
        )

        response = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}")

        linha_nacional = _linha(response, nacional)
        assert Decimal(linha_nacional["valor_distribuido"]) == Decimal("4000")
        assert Decimal(linha_nacional["saldo_disponivel"]) == Decimal("5000")
        # O remanejamento aceita sair o que não está comprometido nem executado, mesmo já distribuído.
        assert Decimal(linha_nacional["saldo_pool"]) == Decimal("9000")
        linha_estadual = _linha(response, estadual)
        assert Decimal(linha_estadual["valor_distribuido"]) == Decimal("1500")
        assert Decimal(linha_estadual["saldo_disponivel"]) == Decimal("2500")

    def test_rubrica_inativa_nao_aparece(self, auth_client_super_admin):
        ativa = _pool_nacional(valor_alocado=Decimal("10"))
        inativa = _pool_nacional(BudgetRubricaFactory(ativo=False), valor_alocado=Decimal("10"))

        response = auth_client_super_admin.get(PAINEL_URL)

        ids = {linha["id"] for linha in response.data}
        assert ativa.pk in ids
        assert inativa.pk not in ids


class TestPainelSemaforo:
    @pytest.mark.parametrize(
        ("comprometido", "semaforo", "alerta"),
        [
            ("5000", "verde", False),
            ("7000", "amarelo", False),
            ("8000", "amarelo", False),
            ("9000", "vermelho", True),
        ],
    )
    def test_faixas(self, auth_client_super_admin, comprometido, semaforo, alerta):
        pool = _pool_nacional(valor_alocado=Decimal("10000"), valor_comprometido=Decimal(comprometido))

        response = auth_client_super_admin.get(PAINEL_URL)

        linha = _linha(response, pool)
        assert linha["semaforo"] == semaforo
        assert linha["alerta_80"] is alerta

    def test_semaforo_segue_limiares_configurados_no_core(self, auth_client_super_admin):
        from django.core.cache import cache

        from apps.core.models.system_config import SystemConfig, TipoConfiguracao

        pool = _pool_nacional(valor_alocado=Decimal("10000"), valor_comprometido=Decimal("8000"))
        SystemConfig.objects.update_or_create(
            chave="budget_alert_red_pct", defaults={"valor": "75", "tipo": TipoConfiguracao.INTEGER},
        )
        try:
            response = auth_client_super_admin.get(PAINEL_URL)

            linha = _linha(response, pool)
            assert linha["semaforo"] == "vermelho"
            assert linha["alerta_80"] is True
        finally:
            # Cache de SystemConfig não é transacional — limpa pra não vazar
            # o limiar de 75% pros testes seguintes.
            cache.delete("system_config:budget_alert_red_pct")

    def test_pool_zerado_nao_quebra(self, auth_client_super_admin):
        pool = _pool_nacional(valor_alocado=Decimal("0"), valor_comprometido=Decimal("0"))

        response = auth_client_super_admin.get(PAINEL_URL)

        assert response.status_code == 200
        linha = _linha(response, pool)
        assert linha["semaforo"] == "verde"
        assert Decimal(linha["valor_aprovado"]) == Decimal("0")


class TestPainelLimiares:
    def test_cada_linha_traz_os_limiares_padrao_como_inteiros(self, auth_client_super_admin):
        _pool_nacional(valor_alocado=Decimal("10"))

        response = auth_client_super_admin.get(PAINEL_URL)

        assert response.status_code == 200
        assert len(response.data) > 0
        assert all(
            linha["limiares_semaforo"] == {"amarelo": 70, "vermelho": 90}
            for linha in response.data
        )
        assert isinstance(response.data[0]["limiares_semaforo"]["amarelo"], int)

    def test_limiares_seguem_o_configurado_no_core(self, auth_client_super_admin):
        from django.core.cache import cache

        from apps.core.models.system_config import SystemConfig, TipoConfiguracao

        _pool_nacional(valor_alocado=Decimal("10"))
        SystemConfig.objects.update_or_create(
            chave="budget_alert_yellow_pct", defaults={"valor": "60", "tipo": TipoConfiguracao.INTEGER},
        )
        SystemConfig.objects.update_or_create(
            chave="budget_alert_red_pct", defaults={"valor": "85", "tipo": TipoConfiguracao.INTEGER},
        )
        try:
            response = auth_client_super_admin.get(PAINEL_URL)

            assert response.status_code == 200
            assert all(
                linha["limiares_semaforo"] == {"amarelo": 60, "vermelho": 85}
                for linha in response.data
            )
        finally:
            # Cache de SystemConfig não é transacional — limpa pra não vazar
            # os limiares alterados pros testes seguintes.
            cache.delete("system_config:budget_alert_yellow_pct")
            cache.delete("system_config:budget_alert_red_pct")

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_articulador_rn"])
    def test_perfis_sem_acesso_ao_system_config_recebem_os_limiares(self, request, cliente, territory_rn):
        BudgetPoolFactory(nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn, valor_alocado=Decimal("10"))

        response = request.getfixturevalue(cliente).get(PAINEL_URL)

        assert response.status_code == 200
        assert len(response.data) > 0
        assert response.data[0]["limiares_semaforo"] == {"amarelo": 70, "vermelho": 90}


class TestPainelFiltros:
    def test_filtros(self, auth_client_super_admin, state_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        outra = BudgetRubricaFactory()
        _pool_nacional(rubrica, valor_alocado=Decimal("9000"))
        _pool_nacional(outra, valor_alocado=Decimal("9000"))
        estadual = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("3000"),
        )
        territorial = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1000"),
        )

        por_rubrica = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}")
        assert {linha["rubrica"]["id"] for linha in por_rubrica.data} == {rubrica.pk}

        por_nivel = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}&nivel=estadual")
        assert [linha["id"] for linha in por_nivel.data] == [estadual.pk]

        por_estado = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}&estado={state_rn.sigla}")
        assert [linha["id"] for linha in por_estado.data] == [estadual.pk, territorial.pk]

        por_territorio = auth_client_super_admin.get(f"{PAINEL_URL}?rubrica={rubrica.slug}&territorio={territory_rn.pk}")
        assert [linha["id"] for linha in por_territorio.data] == [territorial.pk]

    def test_territorio_tem_precedencia_sobre_estado_quando_os_dois_vem(
        self, auth_client_super_admin, state_rn, territory_rn,
    ):
        BudgetPoolFactory(nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn, valor_alocado=Decimal("10"))

        response = auth_client_super_admin.get(
            f"{PAINEL_URL}?estado={state_rn.sigla}&territorio={territory_rn.pk}"
        )

        assert response.status_code == 200
        assert len(response.data) > 0
        assert all(linha["nivel"] == "territorial" for linha in response.data)

    def test_nivel_invalido_e_400(self, auth_client_super_admin):
        assert auth_client_super_admin.get(f"{PAINEL_URL}?nivel=municipal").status_code == 400


class TestPainelMetaComoRelatorio:
    def _executar_na_meta(self, pool, meta, valor):
        acao = WorkPlanAcaoFactory(meta=meta)
        usuario = UserFactory()
        activity = ActivityFactory(acao=acao)
        chave = f"demanda-{meta.pk}-{pool.pk}"
        budget_service.reservar(pool=pool, valor=valor, demand_request_id=chave, usuario=usuario, activity_id=activity.pk)
        budget_service.executar(demand_request_id=chave, usuario=usuario)

    def test_meta_acrescenta_o_executado_sem_recortar_o_saldo(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory(numero=1)
        outra_meta = WorkPlanMetaFactory(numero=2)
        pool = _pool_nacional(valor_alocado=Decimal("1000"))
        self._executar_na_meta(pool, meta, Decimal("100"))
        self._executar_na_meta(pool, outra_meta, Decimal("300"))

        response = auth_client_super_admin.get(f"{PAINEL_URL}?meta={meta.pk}")

        linha = _linha(response, pool)
        assert Decimal(linha["valor_executado_meta"]) == Decimal("100")
        assert Decimal(linha["valor_executado"]) == Decimal("400")
        assert Decimal(linha["valor_aprovado"]) == Decimal("1000")

    def test_sem_meta_nao_traz_o_campo(self, auth_client_super_admin):
        pool = _pool_nacional(valor_alocado=Decimal("1000"))

        response = auth_client_super_admin.get(PAINEL_URL)

        assert "valor_executado_meta" not in _linha(response, pool)

    def test_meta_sem_execucao_traz_zero(self, auth_client_super_admin):
        pool = _pool_nacional(valor_alocado=Decimal("1000"))

        response = auth_client_super_admin.get(f"{PAINEL_URL}?meta={WorkPlanMetaFactory().pk}")

        assert Decimal(_linha(response, pool)["valor_executado_meta"]) == Decimal("0")

    def test_painel_de_um_nivel_acrescenta_o_executado_da_meta(self):
        meta = WorkPlanMetaFactory(numero=1)
        rubrica = BudgetRubricaFactory()
        pool = _pool_nacional(rubrica, valor_alocado=Decimal("1000"))
        self._executar_na_meta(pool, meta, Decimal("100"))

        linhas = budget_service.painel_orcamento(nivel=Nivel.NACIONAL, rubrica_slug=rubrica.slug, meta_id=meta.pk)

        assert linhas[0]["valor_executado_meta"] == Decimal("100")
        assert linhas[0]["valor_executado"] == Decimal("100")


class TestPainelEscopoTerritorial:
    def test_usuario_sem_perfil_no_sgp_recebe_403(self, auth_client_sem_acesso):
        response = auth_client_sem_acesso.get(PAINEL_URL)

        assert response.status_code == 403

    def test_sem_perfil_no_sgp_nao_traz_o_code_de_sem_territorio(self, auth_client_sem_acesso):
        response = auth_client_sem_acesso.get(PAINEL_URL)

        assert "code" not in response.data

    @pytest.mark.parametrize("slug", ["adt-acr", "articulador-estadual"])
    def test_perfil_sem_territorio_vinculado_recebe_code_proprio(self, api_client, slug):
        from apps.core.tests.factories import RoleFactory, TerritoryFactory

        territorio_vazio = TerritoryFactory(nome=f"Território sem estado {slug}", estados=[])
        territorio = None if slug == "adt-acr" else territorio_vazio
        usuario = UserFactory(profiles=[(RoleFactory(slug=slug), territorio)])
        api_client.force_authenticate(user=usuario)

        response = api_client.get(PAINEL_URL)

        assert response.status_code == 403
        assert response.data["code"] == "SEM_TERRITORIO"
        assert response.data["detail"]

    def test_escopo_do_adt(self, auth_client_adt_rn, state_rn, territory_ce, territory_rn):
        rubrica = BudgetRubricaFactory()
        _pool_nacional(rubrica, valor_alocado=Decimal("10"))
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None)
        proprio = BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn)
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_ce)

        outro_territorio = auth_client_adt_rn.get(f"{PAINEL_URL}?territorio={territory_ce.pk}")
        assert outro_territorio.status_code == 403

        proprio_territorio = auth_client_adt_rn.get(f"{PAINEL_URL}?territorio={territory_rn.pk}")
        assert [linha["id"] for linha in proprio_territorio.data] == [proprio.pk]

        sem_filtro = auth_client_adt_rn.get(PAINEL_URL)
        assert [linha["id"] for linha in sem_filtro.data] == [proprio.pk]

        sem_acesso_estadual = auth_client_adt_rn.get(f"{PAINEL_URL}?estado={state_rn.sigla}")
        assert sem_acesso_estadual.status_code == 403

        # `territorio` não resgata: ADT/ACR não tem nível estadual, mesmo mandando
        # o próprio território junto.
        estado_com_proprio_territorio = auth_client_adt_rn.get(
            f"{PAINEL_URL}?estado={state_rn.sigla}&territorio={territory_rn.pk}"
        )
        assert estado_com_proprio_territorio.status_code == 403

    def test_articulador_ve_nacional_e_o_proprio_estado(
        self, auth_client_articulador_rn, state_rn, state_ce, territory_rn, territory_ce,
    ):
        rubrica = BudgetRubricaFactory()
        nacional = _pool_nacional(rubrica, valor_alocado=Decimal("10"))
        estadual = BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None)
        territorial = BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn)
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None)
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_ce)

        sem_filtro = auth_client_articulador_rn.get(PAINEL_URL)
        assert [linha["id"] for linha in sem_filtro.data] == [nacional.pk, estadual.pk, territorial.pk]

        proprio_estado = auth_client_articulador_rn.get(f"{PAINEL_URL}?estado={state_rn.sigla}")
        assert [linha["id"] for linha in proprio_estado.data] == [estadual.pk, territorial.pk]

        proprio_territorio = auth_client_articulador_rn.get(f"{PAINEL_URL}?territorio={territory_rn.pk}")
        assert [linha["id"] for linha in proprio_territorio.data] == [territorial.pk]

        assert auth_client_articulador_rn.get(f"{PAINEL_URL}?estado={state_ce.sigla}").status_code == 403
        assert auth_client_articulador_rn.get(f"{PAINEL_URL}?territorio={territory_ce.pk}").status_code == 403

    def test_fgd_le_a_matriz_como_a_ugp(self, auth_client_fgd, state_rn):
        nacional = _pool_nacional(valor_alocado=Decimal("100"))
        estadual = BudgetPoolFactory(
            rubrica=nacional.rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("10"),
        )

        response = auth_client_fgd.get(PAINEL_URL)

        assert response.status_code == 200
        assert {linha["id"] for linha in response.data} >= {nacional.pk, estadual.pk}

    def test_ugp_recebe_o_id_do_pool_nacional_para_a_origem_do_excedente(self, auth_client_super_admin):
        nacional = _pool_nacional(valor_alocado=Decimal("100"))

        response = auth_client_super_admin.get(f"{PAINEL_URL}?nivel=nacional")

        assert [linha["id"] for linha in response.data] == [nacional.pk]

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


class TestPainelDeUmNivel:
    def test_uma_linha_por_rubrica_ativa_mesmo_sem_pool(self):
        linhas = budget_service.painel_orcamento(nivel=Nivel.NACIONAL)

        assert len(linhas) == BudgetRubrica.objects.filter(ativo=True).count()
        assert all(linha["valor_aprovado"] == Decimal("0") for linha in linhas)

    def test_soma_os_pools_do_nivel_pedido(self, state_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("3000"),
        )
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1000"),
        )

        linhas = budget_service.painel_orcamento(
            nivel=Nivel.ESTADUAL, estado_sigla=state_rn.sigla, rubrica_slug=rubrica.slug,
        )

        assert linhas[0]["valor_aprovado"] == Decimal("3000")
        assert linhas[0]["valor_distribuido"] == Decimal("1000")


class TestBudgetThresholdAlertTask:
    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_task_notifica_vermelhos(
        self, mocked_delay, usuario, usuario_super_admin, django_capture_on_commit_callbacks,
    ):
        rubrica = BudgetRubricaFactory()
        _pool_nacional(rubrica, valor_alocado=Decimal("10000"), valor_comprometido=Decimal("9000"))

        # Notification.save() só enfileira o e-mail via transaction.on_commit
        # — captura os callbacks pra executá-los aqui.
        with django_capture_on_commit_callbacks(execute=True):
            total = check_budget_threshold_alert()

        assert total == 2
        assert mocked_delay.call_count == 2
        notifications = usuario.notifications.filter(evento="budget_allocation_red")
        assert notifications.count() == 1
        assert rubrica.nome in notifications.first().titulo

    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_task_notifica_vermelhos_em_qualquer_nivel(
        self, mocked_delay, usuario, usuario_super_admin, state_rn, territory_rn,
    ):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado=state_rn, territorio=None,
            valor_alocado=Decimal("10000"), valor_comprometido=Decimal("9000"),
        )
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL,
            estado=None, territorio=territory_rn,
            valor_alocado=Decimal("1000"), valor_comprometido=Decimal("100"),
        )

        total = check_budget_threshold_alert()

        assert total == 2
        notifications = usuario.notifications.filter(evento="budget_allocation_red")
        assert notifications.count() == 1

    @patch("apps.core.tasks.notifications.send_email_notification.delay")
    def test_does_not_notify_when_nothing_is_red(self, mocked_delay, usuario):
        _pool_nacional(valor_alocado=Decimal("10000"), valor_comprometido=Decimal("5000"))

        assert check_budget_threshold_alert() == 0
        assert mocked_delay.call_count == 0

    def test_schedule_runs_daily(self, settings):
        schedule = settings.CELERY_BEAT_SCHEDULE["check_budget_threshold_alert"]

        assert schedule["task"] == "sgp.tasks.check_budget_threshold_alert"


class TestPainelPerformance:
    @pytest.fixture(autouse=True)
    def _limiares_em_cache(self):
        # Os limiares do semáforo vêm do SystemConfig via cache, que persiste
        # entre testes — sem aquecer aqui, a contagem mudaria (+2) conforme
        # a ordem em que os testes rodam. As linhas da migration somem quando um
        # teste transacional esvazia a base, e sem linha o `get_config` não guarda
        # o padrão no cache: por isso são recriadas antes de aquecer.
        from django.core.cache import cache

        from apps.core.models.system_config import SystemConfig, TipoConfiguracao

        for chave, valor in (("budget_alert_yellow_pct", "70"), ("budget_alert_red_pct", "90")):
            SystemConfig.objects.get_or_create(chave=chave, defaults={"valor": valor, "tipo": TipoConfiguracao.INTEGER})
            cache.delete(f"system_config:{chave}")
        budget_service.limiares_semaforo()

    @pytest.mark.performance
    def test_queries_nao_crescem_com_os_pools(
        self, auth_client_super_admin, django_assert_max_num_queries, state_rn, territory_rn,
    ):
        for rubrica in BudgetRubrica.objects.filter(ativo=True):
            _pool_nacional(rubrica, valor_alocado=Decimal("1000"))
            BudgetPoolFactory(
                rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("500"),
            )
            BudgetPoolFactory(
                rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
                valor_alocado=Decimal("200"),
            )

        # 2 de perfil, pools e o distribuído, com os 5 da visão total em volta dele.
        with django_assert_max_num_queries(9):
            response = auth_client_super_admin.get(PAINEL_URL)

        assert response.status_code == 200
        assert len(response.data) == 18

    def test_queries_com_todos_os_filtros_do_articulador(
        self, auth_client_articulador_rn, django_assert_max_num_queries, state_rn, territory_rn,
    ):
        meta = WorkPlanMetaFactory()
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, estado=None, territorio=territory_rn,
            valor_alocado=Decimal("200"),
        )

        # Validação dos 4 filtros, perfil, posse do território, pools, a visão total e o executado da Meta.
        with django_assert_max_num_queries(13):
            response = auth_client_articulador_rn.get(
                f"{PAINEL_URL}?meta={meta.pk}&rubrica={rubrica.slug}"
                f"&estado={state_rn.sigla}&territorio={territory_rn.pk}"
            )

        assert response.status_code == 200
