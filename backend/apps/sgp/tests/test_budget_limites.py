from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.db import IntegrityError, transaction
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.budget import limites
from apps.sgp.models import BudgetPool, BudgetTransaction, SpendingLimit
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, SpendingLimitFactory

pytestmark = pytest.mark.django_db

Escopo = SpendingLimit.Escopo
URL = "/api/v1/sgp/orcamento/limites/"


@pytest.fixture
def configurar():
    chaves = []

    def definir(chave, valor, tipo=TipoConfiguracao.BOOLEAN):
        SystemConfig.objects.update_or_create(chave=chave, defaults={"valor": valor, "tipo": tipo})
        chaves.append(chave)

    yield definir
    # Cache de SystemConfig não é transacional: limpa pra não vazar pros testes seguintes.
    for chave in chaves:
        cache.delete(f"system_config:{chave}")


@pytest.fixture
def role_adt(db):
    return RoleFactory(slug="adt-acr", nome="ADT / ACR")


@pytest.fixture
def adt(role_adt, territory_rn):
    return UserFactory(profiles=[(role_adt, territory_rn)])


@pytest.fixture
def rubrica(db):
    return BudgetRubricaFactory()


def _padrao(perfil, rubrica, valor="1000", inicio=date(2026, 1, 1), fim=limites.FIM_EM_ABERTO):
    return SpendingLimit.objects.create(
        escopo=Escopo.PERFIL, perfil=perfil, rubrica=rubrica, valor_limite=Decimal(valor),
        periodo_inicio=inicio, periodo_fim=fim,
    )


class TestPeriodo:
    @pytest.mark.parametrize(
        ("periodicidade", "inicio", "fim"),
        [
            ("mensal", date(2026, 11, 1), date(2026, 11, 30)),
            ("trimestral", date(2026, 10, 1), date(2026, 12, 31)),
            ("semestral", date(2026, 7, 1), date(2026, 12, 31)),
            ("vigencia", limites.INICIO_DA_VIGENCIA, limites.FIM_EM_ABERTO),
        ],
    )
    def test_periodo_contem_a_data(self, periodicidade, inicio, fim):
        assert limites.periodo_de(date(2026, 11, 3), periodicidade) == (inicio, fim)

    def test_periodicidade_vem_do_parametro_global(self, configurar):
        configurar("budget_limit_period", "mensal", TipoConfiguracao.STRING)

        assert limites.periodo_de(date(2026, 2, 10)) == (date(2026, 2, 1), date(2026, 2, 28))


@freeze_time("2026-11-03")
class TestLimiteEfetivo:
    def test_herda_do_perfil_sem_gravar(self, adt, role_adt, rubrica):
        _padrao(role_adt, rubrica, "1000")

        limite = limites.limite_efetivo(adt.pk, rubrica.pk)

        assert limite.pk is None
        assert limite.herdado is True
        assert limite.valor_limite == Decimal("1000")
        assert (limite.periodo_inicio, limite.periodo_fim) == (date(2026, 10, 1), date(2026, 12, 31))
        assert not SpendingLimit.objects.filter(user=adt).exists()

    def test_sobrescrita_vigente_vence_o_padrao(self, adt, role_adt, rubrica):
        _padrao(role_adt, rubrica, "1000")
        sobrescrita = SpendingLimitFactory(user=adt, rubrica=rubrica, valor_limite=Decimal("3000"))

        limite = limites.limite_efetivo(adt.pk, rubrica.pk)

        assert limite.pk == sobrescrita.pk
        assert limite.valor_limite == Decimal("3000")

    def test_sobrescrita_de_outro_periodo_nao_vale(self, adt, role_adt, rubrica):
        _padrao(role_adt, rubrica, "1000")
        SpendingLimitFactory(
            user=adt, rubrica=rubrica, valor_limite=Decimal("3000"),
            periodo_inicio=date(2026, 7, 1), periodo_fim=date(2026, 9, 30),
        )

        assert limites.limite_efetivo(adt.pk, rubrica.pk).valor_limite == Decimal("1000")

    def test_com_dois_perfis_vale_o_maior_padrao(self, role_adt, territory_rn, rubrica):
        articulador = RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")
        usuario = UserFactory(profiles=[(role_adt, territory_rn), (articulador, territory_rn)])
        _padrao(role_adt, rubrica, "1000")
        _padrao(articulador, rubrica, "4000")

        assert limites.limite_efetivo(usuario.pk, rubrica.pk).valor_limite == Decimal("4000")

    def test_sem_limite_nem_padrao_nao_ha_limite(self, adt, rubrica):
        assert limites.limite_efetivo(adt.pk, rubrica.pk) is None


@freeze_time("2026-11-03")
class TestLinhaDoPeriodo:
    def test_primeira_reserva_cria_a_linha_uma_vez_so(self, adt, role_adt, territory_rn, rubrica):
        _padrao(role_adt, rubrica, "1000")

        primeira = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)
        segunda = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        assert primeira.pk == segunda.pk
        assert primeira.herdado is True
        assert primeira.territorio_id == territory_rn.pk
        assert SpendingLimit.objects.filter(user=adt).count() == 1

    def test_sem_criar_nao_gera_a_linha(self, adt, role_adt, rubrica):
        _padrao(role_adt, rubrica, "1000")

        assert limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk) is None
        assert not SpendingLimit.objects.filter(user=adt).exists()

    def test_sem_padrao_nao_gera_a_linha(self, adt, rubrica):
        assert limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True) is None


class TestViradaDePeriodo:
    def _linha_do_trimestre_anterior(self, adt, rubrica, *, comprometido="0", executado="200"):
        with freeze_time("2026-11-03"):
            return SpendingLimitFactory(
                user=adt, rubrica=rubrica, valor_limite=Decimal("1000"),
                valor_comprometido=Decimal(comprometido), valor_executado=Decimal(executado),
            )

    def test_sem_acumulo_o_saldo_expira(self, adt, role_adt, rubrica, configurar):
        configurar("budget_limit_carry_over", "False")
        _padrao(role_adt, rubrica, "1000")
        self._linha_do_trimestre_anterior(adt, rubrica)

        with freeze_time("2027-01-05"):
            limite = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        assert limite.valor_limite == Decimal("1000")
        assert limite.periodo_inicio == date(2027, 1, 1)

    def test_com_acumulo_soma_o_saldo_do_periodo_anterior(self, adt, role_adt, rubrica, configurar):
        configurar("budget_limit_carry_over", "True")
        _padrao(role_adt, rubrica, "1000")
        self._linha_do_trimestre_anterior(adt, rubrica, executado="200")

        with freeze_time("2027-01-05"):
            limite = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        assert limite.valor_limite == Decimal("1800")

    def test_acumulo_sem_padrao_gera_a_linha_so_com_o_saldo(self, adt, rubrica, configurar):
        configurar("budget_limit_carry_over", "True")
        self._linha_do_trimestre_anterior(adt, rubrica, executado="200")

        with freeze_time("2027-01-05"):
            limite = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        assert limite.valor_limite == Decimal("800")
        assert limite.herdado is True

    def test_linha_criada_abre_o_ledger_com_o_valor_e_o_acumulado(self, adt, role_adt, rubrica, configurar):
        configurar("budget_limit_carry_over", "True")
        _padrao(role_adt, rubrica, "1000")
        self._linha_do_trimestre_anterior(adt, rubrica, executado="200")

        with freeze_time("2027-01-05"):
            limite = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        transacao = BudgetTransaction.objects.get(spending_limit=limite)
        assert transacao.tipo == "aumento_limite"
        assert transacao.valor == Decimal("1800")
        assert (transacao.saldo_anterior, transacao.saldo_posterior) == (Decimal("0"), Decimal("1800"))

    def test_acumulo_nao_desconta_saldo_negativo(self, adt, role_adt, rubrica, configurar):
        configurar("budget_limit_carry_over", "True")
        _padrao(role_adt, rubrica, "1000")
        self._linha_do_trimestre_anterior(adt, rubrica, comprometido="1500", executado="0")

        with freeze_time("2027-01-05"):
            limite = limites.limite_efetivo(adt.pk, rubrica.pk)

        assert limite.valor_limite == Decimal("1000")


class TestConstraints:
    @pytest.mark.parametrize("campo", ["valor_limite", "valor_comprometido", "valor_executado"])
    def test_valores_negativos_sao_recusados(self, campo):
        with pytest.raises(IntegrityError), transaction.atomic():
            SpendingLimitFactory(**{campo: Decimal("-1")})

    def test_sobrescrita_sem_justificativa_e_recusada(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            SpendingLimitFactory(justificativa="", herdado=False)

    def test_linha_herdada_dispensa_justificativa(self):
        assert SpendingLimitFactory(justificativa="", herdado=True).pk

    def test_padrao_nao_pode_ter_usuario(self, role_adt):
        with pytest.raises(IntegrityError), transaction.atomic():
            SpendingLimitFactory(escopo=Escopo.PERFIL, perfil=role_adt)

    def test_periodo_invertido_e_recusado(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            SpendingLimitFactory(periodo_inicio=date(2026, 12, 31), periodo_fim=date(2026, 10, 1))

    def test_uma_linha_por_usuario_rubrica_e_periodo(self, adt, rubrica):
        SpendingLimitFactory(user=adt, rubrica=rubrica)

        with pytest.raises(IntegrityError), transaction.atomic():
            SpendingLimitFactory(user=adt, rubrica=rubrica)

    def test_transacao_precisa_de_pool_ou_limite_e_nao_dos_dois(self):
        pool = BudgetPoolFactory()
        limite = SpendingLimitFactory()

        for campos in ({}, {"pool": pool, "spending_limit": limite}):
            with pytest.raises(IntegrityError), transaction.atomic():
                BudgetTransaction.objects.create(tipo="ajuste", valor=1, **campos)


@freeze_time("2026-11-03")
class TestCadastroDoPadrao:
    def test_alteracao_de_padrao_em_uso_vale_a_partir_do_periodo_seguinte(self, adt, role_adt, rubrica, usuario):
        padrao = _padrao(role_adt, rubrica, "1000")
        limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        novo = limites.alterar_padrao(padrao.pk, valor_limite=Decimal("2000"), justificativa="Revisão.", usuario=usuario)

        padrao.refresh_from_db()
        assert padrao.valor_limite == Decimal("1000")
        assert padrao.periodo_fim == date(2026, 12, 31)
        assert novo.valor_limite == Decimal("2000")
        assert novo.periodo_inicio == date(2027, 1, 1)
        assert limites.limite_efetivo(adt.pk, rubrica.pk).valor_limite == Decimal("1000")
        with freeze_time("2027-01-05"):
            assert limites.limite_efetivo(adt.pk, rubrica.pk).valor_limite == Decimal("2000")

    def test_padrao_sem_uso_e_corrigido_no_proprio_registro(self, adt, role_adt, rubrica, usuario):
        padrao = _padrao(role_adt, rubrica, "1000")

        novo = limites.alterar_padrao(padrao.pk, valor_limite=Decimal("2000"), justificativa="Correção.", usuario=usuario)

        assert novo.pk == padrao.pk
        assert limites.limite_efetivo(adt.pk, rubrica.pk).valor_limite == Decimal("2000")

    def test_na_vigencia_do_ted_corrige_o_proprio_registro(self, adt, role_adt, rubrica, usuario, configurar):
        """Com período único não há período seguinte: sem isso, o início viraria 2100-01-01."""
        configurar("budget_limit_period", "vigencia", TipoConfiguracao.STRING)
        padrao = _padrao(role_adt, rubrica, "1000")
        limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        novo = limites.alterar_padrao(padrao.pk, valor_limite=Decimal("2000"), justificativa="Revisão.", usuario=usuario)

        assert novo.pk == padrao.pk
        assert novo.valor_limite == Decimal("2000")
        assert novo.periodo_fim == limites.FIM_EM_ABERTO

    def test_padrao_encerrado_nao_pode_ser_alterado(self, role_adt, rubrica, usuario):
        padrao = _padrao(role_adt, rubrica, "1000", fim=date(2026, 9, 30))

        with pytest.raises(ValidationError):
            limites.alterar_padrao(padrao.pk, valor_limite=Decimal("2000"), justificativa="x", usuario=usuario)

    def test_alteracao_de_valor_exige_justificativa(self, role_adt, rubrica, usuario):
        padrao = _padrao(role_adt, rubrica, "1000")

        with pytest.raises(ValidationError):
            limites.alterar_padrao(padrao.pk, valor_limite=Decimal("2000"), justificativa=" ", usuario=usuario)


@freeze_time("2026-11-03")
class TestSobrescrita:
    def test_sobre_linha_herdada_reaproveita_a_linha(self, adt, role_adt, rubrica, usuario):
        _padrao(role_adt, rubrica, "1000")
        herdada = limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)
        SpendingLimit.objects.filter(pk=herdada.pk).update(valor_comprometido=Decimal("300"))

        limite = limites.criar_sobrescrita(
            user=adt, rubrica=rubrica, valor_limite=Decimal("2000"), justificativa="Mutirão.", usuario=usuario,
        )

        assert limite.pk == herdada.pk
        assert limite.herdado is False
        assert limite.valor_comprometido == Decimal("300")

    def test_grava_no_ledger(self, adt, rubrica, usuario):
        limite = limites.criar_sobrescrita(
            user=adt, rubrica=rubrica, valor_limite=Decimal("2000"), justificativa="Mutirão.", usuario=usuario,
        )
        limites.alterar_sobrescrita(limite.pk, valor_limite=Decimal("1500"), justificativa="Revisão.", usuario=usuario)

        valores = BudgetTransaction.objects.filter(spending_limit=limite).order_by("pk").values_list("tipo", "valor")
        assert list(valores) == [("aumento_limite", Decimal("2000")), ("aumento_limite", Decimal("-500"))]

    def test_sem_justificativa_e_recusada(self, adt, rubrica, usuario):
        with pytest.raises(ValidationError):
            limites.criar_sobrescrita(user=adt, rubrica=rubrica, valor_limite=Decimal("1"), justificativa="", usuario=usuario)

    def test_reducao_preserva_o_ja_comprometido(self, adt, rubrica, usuario):
        limite = SpendingLimitFactory(
            user=adt, rubrica=rubrica, valor_limite=Decimal("1000"), valor_comprometido=Decimal("800"),
        )

        limites.alterar_sobrescrita(limite.pk, valor_limite=Decimal("500"), justificativa="x", usuario=usuario)

        limite.refresh_from_db()
        assert limite.valor_limite == Decimal("500")
        assert limite.valor_comprometido == Decimal("800")
        assert limite.saldo_disponivel == Decimal("-300")

    def test_periodo_no_meio_de_uma_linha_existente_e_recusado(self, adt, rubrica, usuario):
        SpendingLimitFactory(user=adt, rubrica=rubrica, valor_limite=Decimal("1000"), valor_comprometido=Decimal("1000"))

        with pytest.raises(ValidationError):
            limites.criar_sobrescrita(
                user=adt, rubrica=rubrica, valor_limite=Decimal("1000"), justificativa="x", usuario=usuario,
                periodo_inicio=date(2026, 11, 15), periodo_fim=date(2026, 12, 31),
            )

    def test_periodo_diferente_do_da_linha_herdada_e_recusado(self, adt, role_adt, rubrica, usuario):
        _padrao(role_adt, rubrica, "1000")
        limites.travar_limite_vigente(user_id=adt.pk, rubrica_id=rubrica.pk, criar=True)

        with pytest.raises(ValidationError):
            limites.criar_sobrescrita(
                user=adt, rubrica=rubrica, valor_limite=Decimal("2000"), justificativa="x", usuario=usuario,
                periodo_inicio=date(2026, 11, 15), periodo_fim=date(2026, 12, 31),
            )


@freeze_time("2026-11-03")
class TestSobrealocacao:
    def _pool(self, rubrica, territorio, valor="1000"):
        return BudgetPoolFactory(
            rubrica=rubrica, nivel=BudgetPool.Nivel.TERRITORIAL, territorio=territorio, valor_alocado=Decimal(valor),
        )

    def test_desligada_recusa_soma_acima_do_pool(self, adt, rubrica, territory_rn, usuario, configurar):
        configurar("budget_overallocation_allowed", "False")
        self._pool(rubrica, territory_rn, "1000")

        with pytest.raises(ValidationError) as erro:
            limites.criar_sobrescrita(
                user=adt, rubrica=rubrica, valor_limite=Decimal("1500"), justificativa="x", usuario=usuario,
            )

        assert erro.value.detail["soma_limites"] == "1500.00"
        assert erro.value.detail["valor_pool"] == "1000.00"

    def test_desligada_conta_o_padrao_de_cada_usuario(self, adt, role_adt, rubrica, territory_rn, usuario, configurar):
        configurar("budget_overallocation_allowed", "False")
        self._pool(rubrica, territory_rn, "1000")
        UserFactory(profiles=[(role_adt, territory_rn)])

        with pytest.raises(ValidationError):
            limites.criar_padrao(perfil=role_adt, rubrica=rubrica, valor_limite=Decimal("600"), usuario=usuario)

    def test_desligada_nao_recusa_reducao_com_a_soma_ja_acima_do_pool(self, adt, rubrica, territory_rn, usuario, configurar):
        self._pool(rubrica, territory_rn, "100")
        limite = SpendingLimitFactory(user=adt, rubrica=rubrica, territorio=territory_rn, valor_limite=Decimal("800"))
        configurar("budget_overallocation_allowed", "False")

        limites.alterar_sobrescrita(limite.pk, valor_limite=Decimal("700"), justificativa="x", usuario=usuario)

        limite.refresh_from_db()
        assert limite.valor_limite == Decimal("700")

    def test_desligada_trava_o_pool_para_serializar_os_aumentos(self, adt, rubrica, territory_rn, usuario, configurar):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        configurar("budget_overallocation_allowed", "False")
        self._pool(rubrica, territory_rn, "1000")

        with CaptureQueriesContext(connection) as consultas:
            limites.criar_sobrescrita(
                user=adt, rubrica=rubrica, valor_limite=Decimal("500"), justificativa="x", usuario=usuario,
            )

        assert any("FOR UPDATE" in q["sql"] and '"sgp_budgetpool"' in q["sql"] for q in consultas)

    def test_ligada_aceita_soma_acima_do_pool(self, adt, rubrica, territory_rn, usuario, configurar):
        configurar("budget_overallocation_allowed", "True")
        self._pool(rubrica, territory_rn, "1000")

        limite = limites.criar_sobrescrita(
            user=adt, rubrica=rubrica, valor_limite=Decimal("1500"), justificativa="x", usuario=usuario,
        )

        assert limite.valor_limite == Decimal("1500")


class TestParametrosSemeados:
    def test_padroes_do_core(self):
        valores = dict(SystemConfig.objects.filter(chave__startswith="budget_").values_list("chave", "valor"))

        assert valores["budget_limit_period"] == "trimestral"
        assert valores["budget_limit_carry_over"] == "False"
        assert valores["budget_overallocation_allowed"] == "True"


@freeze_time("2026-11-03")
class TestApi:
    def test_adt_nao_acessa(self, auth_client_adt_rn):
        assert auth_client_adt_rn.get(URL).status_code == 403

    def test_cria_padrao_por_perfil(self, auth_client_super_admin, role_adt, rubrica):
        resposta = auth_client_super_admin.post(URL, {
            "escopo": "perfil", "perfil": role_adt.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 201, resposta.data
        assert resposta.data["perfil_slug"] == "adt-acr"
        assert resposta.data["periodo_inicio"] == "2026-10-01"

    def test_padrao_repetido_e_400(self, auth_client_super_admin, role_adt, rubrica):
        _padrao(role_adt, rubrica)

        resposta = auth_client_super_admin.post(URL, {
            "escopo": "perfil", "perfil": role_adt.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 400

    def test_sobrescrita_exige_justificativa(self, auth_client_super_admin, adt, rubrica):
        resposta = auth_client_super_admin.post(URL, {
            "escopo": "individual", "user": adt.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 400
        assert "justificativa" in resposta.data

    def test_escopo_incoerente_e_400(self, auth_client_super_admin, adt, rubrica):
        resposta = auth_client_super_admin.post(URL, {
            "escopo": "perfil", "user": adt.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 400

    def test_lista_os_vigentes_na_data(self, auth_client_super_admin, adt, rubrica):
        atual = SpendingLimitFactory(user=adt, rubrica=rubrica)
        anterior = SpendingLimitFactory(
            user=adt, rubrica=rubrica, periodo_inicio=date(2026, 7, 1), periodo_fim=date(2026, 9, 30),
        )

        hoje = auth_client_super_admin.get(URL, {"user": adt.pk})
        antes = auth_client_super_admin.get(URL, {"user": adt.pk, "data": "2026-08-15"})

        assert [linha["id"] for linha in hoje.data] == [atual.pk]
        assert [linha["id"] for linha in antes.data] == [anterior.pk]

    def test_patch_de_sobrescrita(self, auth_client_super_admin, adt, rubrica):
        limite = SpendingLimitFactory(user=adt, rubrica=rubrica, valor_limite=Decimal("1000"))

        resposta = auth_client_super_admin.patch(
            f"{URL}{limite.pk}/", {"valor_limite": "1500", "justificativa": "Revisão."}, format="json",
        )

        assert resposta.status_code == 200, resposta.data
        assert Decimal(resposta.data["valor_limite"]) == Decimal("1500")

    def test_padrao_so_para_perfil_operacional(self, auth_client_super_admin, rubrica):
        fgd = RoleFactory(slug="fgd", nome="FGD")

        resposta = auth_client_super_admin.post(URL, {
            "escopo": "perfil", "perfil": fgd.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 400
        assert "perfil" in resposta.data

    def test_apagar_territorio_com_limite_nao_e_barrado_pelo_limite(self, adt, rubrica, territory_rn):
        limite = SpendingLimitFactory(user=adt, rubrica=rubrica, territorio=territory_rn)
        adt.profiles.all().delete()

        territory_rn.delete()

        limite.refresh_from_db()
        assert limite.territorio_id is None

    def test_ugp_cadastra(self, api_client, role_adt, rubrica):
        ugp = UserFactory(profiles=[(RoleFactory(slug="ugp", nome="UGP"), None)])
        api_client.force_authenticate(user=ugp)

        resposta = api_client.post(URL, {
            "escopo": "perfil", "perfil": role_adt.pk, "rubrica": rubrica.pk, "valor_limite": "1000",
        }, format="json")

        assert resposta.status_code == 201, resposta.data
