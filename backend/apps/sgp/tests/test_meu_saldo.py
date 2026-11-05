"""Meu saldo, extrato e simulador de remanejamento."""
from datetime import date
from decimal import Decimal

import pytest
from freezegun import freeze_time

from apps.core.tests.factories import UserFactory
from apps.sgp.budget import limites
from apps.sgp.budget import services as budget_service
from apps.sgp.models import BudgetPool, BudgetTransaction, BudgetTransfer
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, SpendingLimitFactory

pytestmark = pytest.mark.django_db

Nivel = BudgetPool.Nivel
Tipo = BudgetTransaction.Tipo
URL = "/api/v1/sgp/orcamento/meu-saldo/"
SIMULAR_URL = "/api/v1/sgp/orcamento/remanejamentos/simular/"
REMANEJAR_URL = "/api/v1/sgp/orcamento/remanejamentos/"


def _limite(user, rubrica=None, *, limite=1000, comprometido=0, executado=0):
    return SpendingLimitFactory(
        user=user, rubrica=rubrica or BudgetRubricaFactory(), valor_limite=limite,
        valor_comprometido=comprometido, valor_executado=executado,
    )


def _mover(limite, tipo, valor, *, comprometido=0, executado=0):
    limite.valor_comprometido += comprometido
    limite.valor_executado += executado
    limite.save(update_fields=["valor_comprometido", "valor_executado"])
    return limites.registrar_movimento(limite=limite, tipo=tipo, valor=Decimal(valor), usuario=limite.user)


def _linha(resposta, rubrica):
    return next(item for item in resposta.json() if item["rubrica"] == rubrica.slug)


# ---------- Meu saldo ----------

class TestMeuSaldo:
    def test_traz_os_valores_e_o_semaforo_por_rubrica(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory(nome="Diárias")
        _limite(usuario_adt_rn, rubrica, limite=1000, comprometido=750, executado=100)

        linha = _linha(auth_client_adt_rn.get(URL), rubrica)

        assert linha["rubrica_nome"] == "Diárias"
        assert (linha["limite"], linha["comprometido"], linha["executado"], linha["disponivel"]) == (
            "1000.00", "750.00", "100.00", "150.00",
        )
        assert linha["semaforo"] == "amarelo"

    @freeze_time("2026-11-05")
    def test_traz_o_periodo_e_os_dias_restantes(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        _limite(usuario_adt_rn, rubrica)

        linha = _linha(auth_client_adt_rn.get(URL), rubrica)

        assert (linha["periodo_inicio"], linha["periodo_fim"]) == ("2026-10-01", "2026-12-31")
        assert linha["dias_restantes"] == (date(2026, 12, 31) - date(2026, 11, 5)).days
        assert linha["acumula_saldo"] is False

    def test_traz_o_saldo_do_pool_do_territorio(self, auth_client_adt_rn, usuario_adt_rn, territory_rn):
        rubrica = BudgetRubricaFactory()
        _limite(usuario_adt_rn, rubrica)
        BudgetPoolFactory(
            rubrica=rubrica, nivel=Nivel.TERRITORIAL, territorio=territory_rn,
            valor_alocado=Decimal("5000"), valor_comprometido=Decimal("1000"),
        )

        assert _linha(auth_client_adt_rn.get(URL), rubrica)["saldo_territorio"] == "4000.00"

    def test_rubrica_sem_pool_no_territorio_vem_sem_saldo_de_territorio(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        _limite(usuario_adt_rn, rubrica)

        assert _linha(auth_client_adt_rn.get(URL), rubrica)["saldo_territorio"] is None

    def test_rubrica_sem_limite_nem_inativa_nao_aparece(self, auth_client_adt_rn, usuario_adt_rn):
        BudgetRubricaFactory(slug="sem-limite")
        inativa = BudgetRubricaFactory(slug="inativa", ativo=False)
        _limite(usuario_adt_rn, inativa)

        slugs = {item["rubrica"] for item in auth_client_adt_rn.get(URL).json()}

        assert not {"sem-limite", "inativa"} & slugs

    def test_so_traz_os_limites_do_proprio_usuario(self, auth_client_adt_rn):
        rubrica = BudgetRubricaFactory()
        _limite(UserFactory(), rubrica)

        assert rubrica.slug not in {item["rubrica"] for item in auth_client_adt_rn.get(URL).json()}

    def test_nao_grava_a_linha_que_o_padrao_do_perfil_geraria(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        limites.criar_padrao(
            perfil=usuario_adt_rn.profiles.get().perfil, rubrica=rubrica, valor_limite=Decimal("800"),
            usuario=UserFactory(),
        )

        linha = _linha(auth_client_adt_rn.get(URL), rubrica)

        assert linha["disponivel"] == "800.00"
        assert not usuario_adt_rn.limites_de_gasto.exists()

    def test_exige_autenticacao(self, api_client):
        assert api_client.get(URL).status_code == 401


# ---------- Extrato ----------

class TestExtrato:
    def _url(self, rubrica):
        return f"{URL}{rubrica.slug}/extrato/"

    def test_a_soma_do_extrato_bate_com_o_saldo_materializado(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        limite = _limite(usuario_adt_rn, rubrica, limite=0)
        limite.valor_limite = Decimal("1000")
        limite.save(update_fields=["valor_limite"])
        limites.registrar_movimento(
            limite=limite, tipo=Tipo.AUMENTO_LIMITE, valor=Decimal("1000"), usuario=usuario_adt_rn,
        )
        _mover(limite, Tipo.RESERVA, "400", comprometido=400)
        _mover(limite, Tipo.AJUSTE, "50", comprometido=50)
        _mover(limite, Tipo.EXECUCAO, "300", comprometido=-450, executado=300)
        _mover(limite, Tipo.LIBERACAO, "150")

        linhas = auth_client_adt_rn.get(self._url(rubrica)).json()["results"]

        limite.refresh_from_db()
        assert limite.saldo_disponivel == Decimal("700")
        assert sum(Decimal(linha["efeito"]) for linha in linhas) == limite.saldo_disponivel

    def test_lista_as_linhas_mais_recentes_primeiro_com_o_periodo(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        limite = _limite(usuario_adt_rn, rubrica)
        primeira = _mover(limite, Tipo.RESERVA, "100", comprometido=100)
        segunda = _mover(limite, Tipo.LIBERACAO, "100", comprometido=-100)

        linhas = auth_client_adt_rn.get(self._url(rubrica)).json()["results"]

        assert [linha["id"] for linha in linhas] == [segunda.pk, primeira.pk]
        assert linhas[0]["tipo"] == "liberacao"
        assert linhas[0]["saldo_posterior"] == "1000.00"
        assert linhas[0]["periodo_inicio"] == limite.periodo_inicio.isoformat()

    def test_pagina_as_linhas(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        limite = _limite(usuario_adt_rn, rubrica)
        for _ in range(3):
            _mover(limite, Tipo.RESERVA, "10", comprometido=10)

        pagina = auth_client_adt_rn.get(self._url(rubrica), {"limit": 2}).json()

        assert pagina["count"] == 3
        assert len(pagina["results"]) == 2
        assert pagina["next"]

    def test_nao_traz_linhas_de_outro_usuario_nem_de_outra_rubrica(self, auth_client_adt_rn, usuario_adt_rn):
        rubrica = BudgetRubricaFactory()
        _mover(_limite(UserFactory(), rubrica), Tipo.RESERVA, "10", comprometido=10)
        _mover(_limite(usuario_adt_rn), Tipo.RESERVA, "10", comprometido=10)

        assert auth_client_adt_rn.get(self._url(rubrica)).json()["results"] == []

    def test_rubrica_inexistente_responde_404(self, auth_client_adt_rn):
        assert auth_client_adt_rn.get(f"{URL}nao-existe/extrato/").status_code == 404


# ---------- Simulador ----------

@pytest.fixture
def pools(state_rn, state_ce):
    rubrica = BudgetRubricaFactory()
    origem = BudgetPoolFactory(
        rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_rn, territorio=None,
        valor_alocado=Decimal("1000"), valor_comprometido=Decimal("500"),
    )
    destino = BudgetPoolFactory(
        rubrica=rubrica, nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None,
        valor_alocado=Decimal("1000"), valor_comprometido=Decimal("950"),
    )
    return origem, destino


def _payload(origem, destino, valor="200.00"):
    return {
        "origem_allocation": origem.pk, "destino_allocation": destino.pk, "valor": valor, "justificativa": "Teste.",
    }


class TestSimulador:
    def test_mostra_saldo_percentual_e_faixa_antes_e_depois(self, auth_client_super_admin, pools):
        resposta = auth_client_super_admin.post(SIMULAR_URL, _payload(*pools), format="json")

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert (corpo["origem"]["saldo_antes"], corpo["origem"]["saldo_depois"]) == ("500.00", "300.00")
        assert (corpo["origem"]["percentual_antes"], corpo["origem"]["percentual_depois"]) == ("50.00", "62.50")
        assert (corpo["origem"]["faixa_antes"], corpo["origem"]["faixa_depois"]) == ("verde", "verde")
        assert (corpo["destino"]["saldo_antes"], corpo["destino"]["saldo_depois"]) == ("50.00", "250.00")
        assert (corpo["destino"]["faixa_antes"], corpo["destino"]["faixa_depois"]) == ("vermelho", "amarelo")

    def test_produz_os_mesmos_numeros_da_execucao_real(self, auth_client_super_admin, pools):
        origem, destino = pools

        simulado = auth_client_super_admin.post(SIMULAR_URL, _payload(origem, destino), format="json").json()
        real = auth_client_super_admin.post(REMANEJAR_URL, _payload(origem, destino), format="json")

        assert real.status_code == 201
        debito, credito = real.json()
        assert (simulado["origem"]["saldo_antes"], simulado["origem"]["saldo_depois"]) == (
            debito["saldo_anterior"], debito["saldo_posterior"],
        )
        assert (simulado["destino"]["saldo_antes"], simulado["destino"]["saldo_depois"]) == (
            credito["saldo_anterior"], credito["saldo_posterior"],
        )
        origem.refresh_from_db()
        assert simulado["origem"]["percentual_depois"] == (
            f"{budget_service.percentual_comprometido(origem.valor_comprometido, origem.valor_alocado):.2f}"
        )

    def test_nao_grava_nenhuma_linha(self, auth_client_super_admin, pools):
        origem, destino = pools
        antes = (BudgetTransaction.objects.count(), BudgetTransfer.objects.count())

        auth_client_super_admin.post(SIMULAR_URL, _payload(origem, destino), format="json")

        assert (BudgetTransaction.objects.count(), BudgetTransfer.objects.count()) == antes
        origem.refresh_from_db()
        destino.refresh_from_db()
        assert (origem.valor_alocado, destino.valor_alocado) == (Decimal("1000"), Decimal("1000"))

    def test_saldo_insuficiente_responde_como_a_execucao_real(self, auth_client_super_admin, pools):
        payload = _payload(*pools, valor="600.00")

        simulado = auth_client_super_admin.post(SIMULAR_URL, payload, format="json")
        real = auth_client_super_admin.post(REMANEJAR_URL, payload, format="json")

        assert simulado.status_code == real.status_code == 400
        assert simulado.json() == real.json()
        assert simulado.json()["code"] == "INSUFFICIENT_BALANCE"

    def test_rubricas_diferentes_sao_recusadas(self, auth_client_super_admin, pools, state_ce):
        outra = BudgetPoolFactory(nivel=Nivel.ESTADUAL, estado=state_ce, territorio=None, valor_alocado=Decimal("10"))

        resposta = auth_client_super_admin.post(SIMULAR_URL, _payload(pools[0], outra), format="json")

        assert resposta.status_code == 400
        assert "destino_allocation" in resposta.json()

    def test_so_ugp_e_super_admin_simulam(self, auth_client_adt_rn, pools):
        assert auth_client_adt_rn.post(SIMULAR_URL, _payload(*pools), format="json").status_code == 403
