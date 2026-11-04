"""O ledger único: saldos anterior e posterior, imutabilidade no banco e RLS por perfil."""
from decimal import Decimal
from io import StringIO

import psycopg2
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, InternalError, connection, transaction

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.core.signals.audit import clear_audit_context, set_audit_context
from apps.sgp.budget import limites
from apps.sgp.budget import services as budget_service
from apps.sgp.budget.rls import visao_total
from apps.sgp.models import BudgetPool, BudgetTransaction, BudgetTransfer, SpendingLimit
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, BudgetTransactionFactory, SpendingLimitFactory

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel
Tipo = BudgetTransaction.Tipo


def _saldo(pool):
    pool.refresh_from_db()
    return pool.valor_alocado - pool.valor_comprometido - pool.valor_executado


class TestSaldoAnteriorEPosterior:
    def test_cada_movimento_do_pool_encadeia_os_saldos(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        budget_service.reservar(pool=pool, valor=Decimal("300"), demand_request_id="s1", usuario=usuario)
        budget_service.ajustar_reserva(demand_request_id="s1", novo_valor=Decimal("400"), usuario=usuario)
        budget_service.executar(demand_request_id="s1", usuario=usuario, valor_executado=Decimal("350"))

        linhas = list(
            pool.transactions.order_by("pk").values_list("tipo", "valor", "saldo_anterior", "saldo_posterior")
        )
        assert linhas == [
            (Tipo.RESERVA, Decimal("300"), Decimal("1000"), Decimal("700")),
            (Tipo.AJUSTE, Decimal("100"), Decimal("700"), Decimal("600")),
            (Tipo.EXECUCAO, Decimal("350"), Decimal("600"), Decimal("600")),
            (Tipo.LIBERACAO, Decimal("50"), Decimal("600"), Decimal("650")),
        ]
        assert linhas[-1][3] == _saldo(pool)

    def test_liberacao_devolve_ao_saldo(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(pool=pool, valor=Decimal("300"), demand_request_id="s2", usuario=usuario)

        transacao = budget_service.liberar(demand_request_id="s2", usuario=usuario, motivo="Cancelada.")

        assert (transacao.saldo_anterior, transacao.saldo_posterior) == (Decimal("700"), Decimal("1000"))

    def test_remanejamento_registra_o_saldo_dos_dois_pools(self, state_rn, state_ce):
        rubrica = BudgetRubricaFactory()
        origem = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("1000"),
        )
        destino = BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None, valor_alocado=Decimal("100"),
        )

        debito, credito = budget_service.remanejar(
            origem=origem, destino=destino, valor=Decimal("300"), usuario=UserFactory(), justificativa="x",
        )

        assert (debito.saldo_anterior, debito.saldo_posterior) == (Decimal("1000"), Decimal("700"))
        assert (credito.saldo_anterior, credito.saldo_posterior) == (Decimal("100"), Decimal("400"))

    def test_criacao_de_pool_parte_de_zero(self):
        pool = budget_service.criar_pool(
            rubrica=BudgetRubricaFactory(), nivel=Nivel.NACIONAL, valor_alocado=Decimal("500"), usuario=UserFactory(),
        )

        transacao = pool.transactions.get()
        assert (transacao.saldo_anterior, transacao.saldo_posterior) == (Decimal("0"), Decimal("500"))

    def test_movimento_do_limite_registra_os_saldos(self):
        limite = SpendingLimitFactory(valor_limite=Decimal("1000"))
        limite.valor_comprometido = Decimal("300")
        limite.save(update_fields=["valor_comprometido"])

        transacao = limites.registrar_movimento(
            limite=limite, tipo=Tipo.RESERVA, valor=Decimal("300"), usuario=UserFactory(), demand_request_id="s3",
        )

        assert (transacao.saldo_anterior, transacao.saldo_posterior) == (Decimal("1000"), Decimal("700"))

    def test_grava_o_ip_do_contexto_da_requisicao(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        set_audit_context(user=usuario, ip="10.0.0.9", user_agent="teste")
        try:
            transacao = budget_service.reservar(pool=pool, valor=Decimal("1"), demand_request_id="s4", usuario=usuario)
        finally:
            clear_audit_context()

        assert transacao.ip == "10.0.0.9"

    def test_reserva_guarda_solicitacao_e_demanda_separadas(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()

        budget_service.reservar(
            pool=pool, valor=Decimal("10"), demand_request_id="42", demanda_id="7", usuario=usuario,
        )
        execucao = budget_service.executar(demand_request_id="42", usuario=usuario)

        assert (execucao.demand_request_id, execucao.demanda_id) == ("42", "7")


class TestConstraints:
    def test_transacao_precisa_de_pool_ou_de_limite(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            BudgetTransaction.objects.create(tipo=Tipo.AJUSTE, valor=Decimal("1"))

    def test_pool_nao_aceita_saldo_negativo(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            BudgetPoolFactory(valor_alocado=Decimal("100"), valor_comprometido=Decimal("80"), valor_executado=Decimal("30"))

    def test_territorial_nao_aceita_estado(self, state_rn, territory_rn):
        with pytest.raises(IntegrityError), transaction.atomic():
            BudgetPoolFactory(nivel=Nivel.TERRITORIAL, estado=state_rn, territorio=territory_rn)

    def test_pool_aceita_saldo_zero(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("100"), valor_comprometido=Decimal("70"), valor_executado=Decimal("30"))

        assert _saldo(pool) == Decimal("0")


class TestImutabilidadeNoBanco:
    """Direto no SQL: o `save()` e o `delete()` do modelo são a primeira barreira, o trigger é a que
    vale para quem passa por fora deles."""

    @pytest.mark.parametrize("sql", ["UPDATE {tabela} SET valor = 1 WHERE id = %s", "DELETE FROM {tabela} WHERE id = %s"])
    def test_transacao_recusa_update_e_delete_em_sql_cru(self, sql):
        transacao = BudgetTransactionFactory()

        with pytest.raises(InternalError, match="imutáveis"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql.format(tabela="sgp_budgettransaction"), [transacao.pk])

    @pytest.mark.parametrize("sql", ["UPDATE {tabela} SET valor = 1 WHERE id = %s", "DELETE FROM {tabela} WHERE id = %s"])
    def test_remanejamento_recusa_update_e_delete_em_sql_cru(self, sql):
        rubrica = BudgetRubricaFactory()
        transferencia = BudgetTransfer.objects.create(
            tipo="entre_niveis", pool_origem=BudgetPoolFactory(rubrica=rubrica), pool_destino=BudgetPoolFactory(rubrica=rubrica),
            valor=Decimal("1"), motivo="x", saldo_origem_antes=0, saldo_origem_depois=0,
            saldo_destino_antes=0, saldo_destino_depois=0,
        )

        with pytest.raises(InternalError, match="imutáveis"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql.format(tabela="sgp_budgettransfer"), [transferencia.pk])

    def test_update_em_massa_do_orm_tambem_e_recusado(self):
        BudgetTransactionFactory()

        with pytest.raises(InternalError, match="imutáveis"), transaction.atomic():
            BudgetTransaction.objects.all().update(valor=Decimal("1"))

    def test_usuario_que_criou_a_transacao_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError

        usuario = UserFactory()
        BudgetTransactionFactory(criado_por=usuario)

        with pytest.raises(ProtectedError):
            usuario.delete()


class TestVerificarSaldos:
    def _rodar(self):
        saida = StringIO()
        call_command("verificar_saldos", stdout=saida)
        return saida.getvalue()

    def test_passa_com_o_saldo_movido_pelo_motor(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        usuario = UserFactory()
        budget_service.reservar(pool=pool, valor=Decimal("300"), demand_request_id="v1", usuario=usuario)
        budget_service.executar(demand_request_id="v1", usuario=usuario, valor_executado=Decimal("200"))

        assert "sem divergência" in self._rodar()

    def test_acusa_saldo_posterior_diferente_do_materializado(self):
        pool = BudgetPoolFactory(valor_alocado=Decimal("1000"))
        budget_service.reservar(pool=pool, valor=Decimal("300"), demand_request_id="v2", usuario=UserFactory())
        BudgetPool.objects.filter(pk=pool.pk).update(valor_alocado=Decimal("900"))

        with pytest.raises(CommandError, match="saldo_posterior"):
            self._rodar()

    def test_acusa_limite_com_comprometido_diferente_do_ledger(self):
        limite = SpendingLimitFactory(valor_limite=Decimal("1000"), user=UserFactory())
        limites.registrar_movimento(limite=limite, tipo=Tipo.AUMENTO_LIMITE, valor=Decimal("1000"), usuario=UserFactory())
        SpendingLimit.objects.filter(pk=limite.pk).update(valor_comprometido=Decimal("50"))

        with pytest.raises(CommandError, match=f"Limite #{limite.pk}"):
            self._rodar()


class TestVisaoTotal:
    def _papel(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.user_role', true)")
            return cursor.fetchone()[0]

    def test_devolve_o_papel_anterior(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.user_role', 'adt-teste', true)")
            with visao_total():
                assert self._papel() == "super-admin"
            assert self._papel() == "adt-teste"

    def test_desfaz_o_papel_quando_o_bloco_falha(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.user_role', 'adt-teste', true)")
            with pytest.raises(ValueError), visao_total():
                raise ValueError
            assert self._papel() == "adt-teste"


_APP_USER = "app_user"
_APP_USER_PASSWORD = "app_pass"
_TABELAS_LEITURA = [
    "sgp_budgetpool", "sgp_spendinglimit", "sgp_budgettransaction", "core_territory", "core_state",
]


def _garantir_app_user():
    """O role de runtime não existe no Postgres efêmero do CI: mesmo padrão de `test_demand_rls`."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", [_APP_USER])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {_APP_USER} LOGIN PASSWORD '{_APP_USER_PASSWORD}';")
        cursor.execute("GRANT USAGE ON SCHEMA public TO app_user;")
        for tabela in _TABELAS_LEITURA:
            cursor.execute(f"GRANT SELECT ON {tabela} TO app_user;")


def _visiveis(tabela, *, user_id=None, role="", territorios="") -> set[int]:
    dsn = connection.settings_dict
    conn = psycopg2.connect(
        dbname=dsn["NAME"], host=dsn["HOST"] or "localhost", port=dsn["PORT"] or 5432,
        user=_APP_USER, password=_APP_USER_PASSWORD,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_user_id = %s;", [str(user_id or "")])
            cursor.execute("SET LOCAL app.user_role = %s;", [role])
            cursor.execute("SET LOCAL app.user_territorios = %s;", [territorios])
            cursor.execute(f"SELECT id FROM {tabela};")  # nome fixo, vindo do próprio teste
            return {linha[0] for linha in cursor.fetchall()}
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.django_db(transaction=True)
class TestRlsPorPerfil:
    @pytest.fixture
    def cenario(self, state_rn, state_ce, territory_rn, territory_ce):
        _garantir_app_user()
        rubrica = BudgetRubricaFactory()
        usuario_rn, usuario_ce = UserFactory(), UserFactory()
        pools = {
            "nacional": BudgetPoolFactory(
                rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=10,
            ),
            "estadual_rn": BudgetPoolFactory(
                rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=10,
            ),
            "estadual_ce": BudgetPoolFactory(
                rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None, valor_alocado=10,
            ),
            "territorial_rn": BudgetPoolFactory(rubrica=rubrica, territorio=territory_rn, valor_alocado=10),
            "territorial_ce": BudgetPoolFactory(rubrica=rubrica, territorio=territory_ce, valor_alocado=10),
        }
        limite_rn = SpendingLimitFactory(user=usuario_rn, rubrica=rubrica, territorio=territory_rn)
        limite_ce = SpendingLimitFactory(user=usuario_ce, rubrica=rubrica, territorio=territory_ce)
        padrao = SpendingLimit.objects.create(
            escopo=SpendingLimit.Escopo.PERFIL, perfil=RoleFactory(slug="adt-acr", nome="ADT / ACR"), rubrica=rubrica,
            valor_limite=1, periodo_inicio=limites.INICIO_DA_VIGENCIA, periodo_fim=limites.FIM_EM_ABERTO,
        )
        transacoes = {
            "pool_rn": BudgetTransactionFactory(pool=pools["territorial_rn"]),
            "pool_ce": BudgetTransactionFactory(pool=pools["territorial_ce"]),
            "limite_rn": BudgetTransaction.objects.create(spending_limit=limite_rn, tipo=Tipo.RESERVA, valor=1),
            "limite_ce": BudgetTransaction.objects.create(spending_limit=limite_ce, tipo=Tipo.RESERVA, valor=1),
        }
        return {
            "pools": pools, "limite_rn": limite_rn, "limite_ce": limite_ce, "padrao": padrao, "transacoes": transacoes,
            "usuario_rn": usuario_rn, "territory_rn": territory_rn,
        }

    def test_adt_ve_o_pool_do_proprio_territorio(self, cenario):
        visiveis = _visiveis("sgp_budgetpool", territorios=str(cenario["territory_rn"].pk))

        assert visiveis == {cenario["pools"]["territorial_rn"].pk}

    def test_adt_sem_territorio_nao_ve_pool(self, cenario):
        assert _visiveis("sgp_budgetpool") == set()

    def test_articulador_ve_o_nacional_e_o_proprio_estado(self, cenario):
        visiveis = _visiveis("sgp_budgetpool", role="articulador-estadual", territorios=str(cenario["territory_rn"].pk))

        pools = cenario["pools"]
        assert visiveis == {pools["nacional"].pk, pools["estadual_rn"].pk, pools["territorial_rn"].pk}

    @pytest.mark.parametrize("role", ["ugp", "fgd", "super-admin"])
    def test_perfis_globais_veem_todos_os_pools(self, cenario, role):
        assert _visiveis("sgp_budgetpool", role=role) == {pool.pk for pool in cenario["pools"].values()}

    def test_usuario_ve_o_proprio_limite_e_os_padroes(self, cenario):
        visiveis = _visiveis("sgp_spendinglimit", user_id=cenario["usuario_rn"].pk)

        assert visiveis == {cenario["limite_rn"].pk, cenario["padrao"].pk}

    def test_articulador_ve_os_limites_do_proprio_estado(self, cenario):
        visiveis = _visiveis(
            "sgp_spendinglimit", role="articulador-estadual", territorios=str(cenario["territory_rn"].pk),
        )

        assert visiveis == {cenario["limite_rn"].pk, cenario["padrao"].pk}

    def test_ugp_ve_todos_os_limites(self, cenario):
        visiveis = _visiveis("sgp_spendinglimit", role="ugp")

        assert {cenario["limite_rn"].pk, cenario["limite_ce"].pk, cenario["padrao"].pk} == visiveis

    def test_transacao_segue_o_criterio_do_pool_ou_do_limite(self, cenario):
        visiveis = _visiveis(
            "sgp_budgettransaction", user_id=cenario["usuario_rn"].pk, territorios=str(cenario["territory_rn"].pk),
        )

        transacoes = cenario["transacoes"]
        assert visiveis == {transacoes["pool_rn"].pk, transacoes["limite_rn"].pk}

    def test_ugp_ve_todas_as_transacoes(self, cenario):
        assert _visiveis("sgp_budgettransaction", role="ugp") == {t.pk for t in cenario["transacoes"].values()}


class TestAgregadosIgnoramOFiltroDoRls:
    """Sob o papel de runtime: os totais são os mesmos para todo perfil. A suíte roda como superusuário,
    que passa por cima do RLS, e não pegaria o recorte sem isto."""

    @pytest.fixture
    def como_runtime(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE ROLE runtime_orcamento_teste NOLOGIN NOBYPASSRLS;")
            cursor.execute("GRANT USAGE ON SCHEMA public TO runtime_orcamento_teste;")
            cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO runtime_orcamento_teste;")

        def entrar(*, role, territorios):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE runtime_orcamento_teste;")
                cursor.execute("SELECT set_config('app.user_role', %s, true)", [role])
                cursor.execute("SELECT set_config('app.user_territorios', %s, true)", [territorios])
                cursor.execute("SELECT set_config('app.current_user_id', '', true)")

        yield entrar
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE;")

    @pytest.fixture
    def rubrica_distribuida(self, state_rn, state_ce):
        rubrica = BudgetRubricaFactory()
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.NACIONAL, estado=None, territorio=None, valor_alocado=Decimal("10000"))
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None, valor_alocado=Decimal("4000"))
        BudgetPoolFactory(rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None, valor_alocado=Decimal("3000"))
        return rubrica

    def test_articulador_ve_o_distribuido_de_todos_os_estados_na_matriz(
        self, como_runtime, rubrica_distribuida, usuario_articulador_rn, territory_rn,
    ):
        como_runtime(role="articulador-estadual", territorios=str(territory_rn.pk))

        linhas = budget_service.matriz_orcamento_para_usuario(usuario_articulador_rn, rubrica_slug=rubrica_distribuida.slug)

        nacional = next(linha for linha in linhas if linha["nivel"] == "nacional")
        assert nacional["valor_distribuido"] == Decimal("7000")
        assert nacional["saldo_disponivel"] == Decimal("3000")
        assert {linha["nivel"] for linha in linhas} == {"nacional", "estadual"}
        assert len(linhas) == 2

    def test_articulador_ve_o_distribuido_de_todos_os_estados_no_painel_de_um_nivel(
        self, como_runtime, rubrica_distribuida, territory_rn,
    ):
        como_runtime(role="articulador-estadual", territorios=str(territory_rn.pk))

        linha = budget_service.painel_orcamento(nivel=Nivel.NACIONAL, rubrica_slug=rubrica_distribuida.slug)[0]

        assert linha["valor_distribuido"] == Decimal("7000")

    def test_adt_ve_o_aprovado_nacional_na_rota_da_meta(self, como_runtime, rubrica_distribuida, usuario_adt_rn, territory_rn):
        como_runtime(role="", territorios=str(territory_rn.pk))

        linhas = budget_service.orcamento_por_rubrica(usuario_adt_rn)

        linha = next(linha for linha in linhas if linha["rubrica"].pk == rubrica_distribuida.pk)
        assert linha["valor_aprovado"] == Decimal("10000")
        assert linha["valor_distribuido"] == Decimal("7000")
        assert linha["detalhamento"] == []
