from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.test.utils import CaptureQueriesContext

from apps.sgd.exceptions import ErroDeDominio, RegraDeNegocio, SaldoInsuficiente
from apps.sgd.models import DemandIndividualLimit, DemandRequest
from apps.sgd.models.demand_request import RESERVA_ATIVA
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services import orcamento as orcamento_service
from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory

pytestmark = pytest.mark.django_db


def test_bloqueio_trava_individual_sem_limite_configurado(solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn):
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, activity=activity_rn, valor=Decimal("100"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "individual"


def test_bloqueio_trava_individual_insuficiente(solicitante_rn, rubrica_diarias, activity_rn, allocation_territorial_rn, limite_individual_rn):
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, activity=activity_rn,
        valor=Decimal("999999"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "individual"


def test_bloqueio_trava_territorial_esgotada(solicitante_rn, rubrica_diarias, activity_rn, limite_individual_rn):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=100, valor_comprometido=100,
    )
    check = balance_service.verificar_duas_travas(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, activity=activity_rn, valor=Decimal("50"),
    )
    assert check.disponivel is False
    assert check.trava_bloqueada == "territorial"


def test_reservar_duas_travas_reserva_nos_dois_lados(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == demand_request_rn.valor_estimado


def test_reservar_duas_travas_idempotente(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == demand_request_rn.valor_estimado


def test_ajustar_duas_travas_valor_menor_libera_diferenca(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = demand_request_rn.valor_estimado - Decimal("300")

    balance_service.ajustar_duas_travas(demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == novo_valor
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == novo_valor


def test_ajustar_duas_travas_acima_do_limite_bloqueia_sem_bypass(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = limite_individual_rn.valor_limite + Decimal("1")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        balance_service.ajustar_duas_travas(demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn)

    assert "Solicitar recurso extra" in str(excinfo.value.como_dict()["detail"])


def test_ajustar_duas_travas_acima_do_pool_territorial_orienta_acionar_articulador(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = allocation_territorial_rn.valor_alocado + Decimal("1")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        balance_service.ajustar_duas_travas(
            demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn,
            ignorar_limite_individual=True,
        )

    assert "Acione o Articulador Estadual" in str(excinfo.value.como_dict()["detail"])
    assert "Território esgotado" in str(excinfo.value.como_dict()["detail"])


def test_ajustar_duas_travas_com_bypass_autoriza_excedente_sem_elevar_limite(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    """RF16: `ignorar_limite_individual=True` autoriza o ajuste pontual acima do
    saldo individual disponível, mas `valor_limite` continua o mesmo."""
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    valor_limite_antes = limite_individual_rn.valor_limite
    novo_valor = valor_limite_antes + Decimal("1")

    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn,
        ignorar_limite_individual=True,
    )

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == novo_valor
    assert limite_individual_rn.valor_limite == valor_limite_antes


def test_liberar_duas_travas_libera_100_por_cento(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Recusada.")

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_executar_duas_travas_valor_pago_menor_libera_diferenca(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.valor_autorizado = demand_request_rn.valor_estimado
    demand_request_rn.save(update_fields=["valor_autorizado"])

    valor_pago = demand_request_rn.valor_estimado - Decimal("200")
    balance_service.executar_duas_travas(demand_request=demand_request_rn, valor_pago=valor_pago, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert limite_individual_rn.valor_executado == valor_pago

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_executado == valor_pago


def test_autorizar_excedente_exige_justificativa(demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn):
    from apps.core.tests.factories import StateFactory
    from apps.sgp.models.budget import BudgetAllocation
    from apps.sgp.tests.factories import BudgetAllocationFactory

    origem = BudgetAllocationFactory(
        meta=demand_request_rn.demanda.activity.acao.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.ESTADUAL, territorio=None,
        estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"), valor_alocado=5000,
    )
    with pytest.raises(ErroDeDominio):
        balance_service.autorizar_excedente(
            demand_request=demand_request_rn, origem_allocation=origem,
            valor_excedente=Decimal("500"), justificativa="", usuario=solicitante_rn,
        )


def test_autorizar_excedente_com_justificativa_remaneja_sem_elevar_limite_individual(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """RF16: o remanejamento emergencial move o pool territorial, mas nunca eleva
    `valor_limite` — senão o solicitante ganharia teto maior permanentemente por
    causa de um excedente pontual."""
    from apps.core.tests.factories import StateFactory
    from apps.sgp.models.budget import BudgetAllocation, BudgetTransaction
    from apps.sgp.tests.factories import BudgetAllocationFactory

    origem = BudgetAllocationFactory(
        meta=demand_request_rn.demanda.activity.acao.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.ESTADUAL, territorio=None,
        estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"), valor_alocado=Decimal("5000"),
    )
    valor_limite_antes = limite_individual_rn.valor_limite

    balance_service.autorizar_excedente(
        demand_request=demand_request_rn, origem_allocation=origem,
        valor_excedente=Decimal("500"), justificativa="Demanda urgente aprovada pela UGP.",
        usuario=solicitante_rn,
    )

    origem.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    limite_individual_rn.refresh_from_db()

    assert origem.valor_alocado == Decimal("4500")
    assert allocation_territorial_rn.valor_alocado == Decimal("10500")
    assert limite_individual_rn.valor_limite == valor_limite_antes
    assert BudgetTransaction.objects.filter(
        allocation=origem, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
    ).exists()


def test_submeter_demanda_bloqueio_de_uma_solicitacao_identifica_so_a_bloqueada(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """§4.1: verificação é rubrica a rubrica — a solicitação sem bloqueio não
    deve aparecer na lista de bloqueios, mesmo a submissão inteira falhando
    (tudo-ou-nada, RF13: nada é reservado até todas passarem)."""
    from apps.sgp.tests.factories import BudgetRubricaFactory

    demand = demand_request_rn.demanda
    rubrica_sem_limite = BudgetRubricaFactory(slug="rubrica-sem-limite-sgd")
    solicitacao_bloqueada = DemandRequestFactory(
        demanda=demand, rubrica=rubrica_sem_limite, tipo="grafico", valor_estimado=Decimal("100"),
        campos_json={
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
        },
    )

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand, usuario=solicitante_rn)

    bloqueios = excinfo.value.como_dict()["solicitacoes_bloqueadas"]
    assert str(solicitacao_bloqueada.pk) in bloqueios
    assert str(demand_request_rn.pk) not in bloqueios
    assert excinfo.value.como_dict()["solicitacao_id"] == solicitacao_bloqueada.pk
    assert excinfo.value.como_dict()["code"] == "INSUFFICIENT_BALANCE"
    assert excinfo.value.como_dict()["trava"] == "individual"

    demand.refresh_from_db()
    assert demand.status == "rascunho"
    assert demand.solicitacoes.count() == 2
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")


def test_submeter_demanda_bloqueio_territorial_orienta_acionar_articulador(
    demand_request_rn, solicitante_rn, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("500"), valor_comprometido=Decimal("0"),
    )

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_request_rn.demanda, usuario=solicitante_rn)

    bloqueio = excinfo.value.como_dict()["solicitacoes_bloqueadas"][str(demand_request_rn.pk)]
    assert bloqueio["trava"] == "territorial"
    assert bloqueio["acao_sugerida"] == "acionar_articulador"
    assert "Acione o Articulador Estadual" in str(bloqueio["detail"])
    # Pool de 500 com 500 livres: o território ainda tem saldo, só não
    # cobre os 1.000 pedidos.
    assert "Território esgotado nesta rubrica para este valor" in str(bloqueio["detail"])


def test_submeter_demanda_bloqueio_individual_orienta_recurso_extra(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("500")
    limite_individual_rn.save(update_fields=["valor_limite"])

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_request_rn.demanda, usuario=solicitante_rn)

    bloqueio = excinfo.value.como_dict()["solicitacoes_bloqueadas"][str(demand_request_rn.pk)]
    assert bloqueio["trava"] == "individual"
    assert bloqueio["acao_sugerida"] == "solicitar_recurso_extra"
    assert "Solicitar recurso extra" in str(bloqueio["detail"])


def _solicitacoes_diaria(demand, rubrica, *valores):
    return [
        DemandRequestFactory(demanda=demand, tipo="diaria", rubrica=rubrica, valor_estimado=Decimal(v))
        for v in valores
    ]


def test_submeter_demanda_pre_checagem_soma_solicitacoes_da_mesma_rubrica_no_limite_individual(
    demand_rascunho_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    """Três de R$ 60 com R$ 100 de limite: cada uma sozinha cabe, juntas não.
    A pré-checagem tem que barrar a segunda e a terceira, não deixar a
    reserva descobrir só a segunda."""
    limite_individual_rn.valor_limite = Decimal("100")
    limite_individual_rn.save(update_fields=["valor_limite"])
    _, segunda, terceira = _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "60", "60", "60")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert set(corpo["solicitacoes_bloqueadas"]) == {str(segunda.pk), str(terceira.pk)}
    assert corpo["solicitacao_id"] == segunda.pk
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "individual"
    assert "R$ 40,00 disponível, R$ 60,00 solicitado" in corpo["detail"]
    assert "Já descontados R$ 60,00 de outras solicitações desta demanda" in corpo["detail"]

    demand_rascunho_rn.refresh_from_db()
    assert demand_rascunho_rn.status == "rascunho"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")


def test_submeter_demanda_pre_checagem_soma_solicitacoes_da_mesma_rubrica_no_pool_territorial(
    demand_rascunho_rn, solicitante_rn, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    allocation = BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("100"), valor_comprometido=Decimal("0"),
    )
    _, segunda, terceira = _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "60", "60", "60")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert set(corpo["solicitacoes_bloqueadas"]) == {str(segunda.pk), str(terceira.pk)}
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "territorial"
    assert "R$ 40,00 disponível, R$ 60,00 solicitado" in corpo["detail"]
    assert "Já descontados R$ 60,00 de outras solicitações desta demanda" in corpo["detail"]
    allocation.refresh_from_db()
    assert allocation.valor_comprometido == Decimal("0")


def test_submeter_demanda_pre_checagem_barrada_nao_consome_saldo_das_seguintes(
    demand_rascunho_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    """60 passa (sobram 40), 60 é barrada, 30 ainda cabe nos 40."""
    limite_individual_rn.valor_limite = Decimal("100")
    limite_individual_rn.save(update_fields=["valor_limite"])
    _, barrada, _ = _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "60", "60", "30")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    assert set(excinfo.value.como_dict()["solicitacoes_bloqueadas"]) == {str(barrada.pk)}


def test_submeter_demanda_limite_zerado_pela_propria_demanda_mostra_valores_e_nao_diz_esgotado(
    demand_rascunho_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("100")
    limite_individual_rn.save(update_fields=["valor_limite"])
    *_, terceira = _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "50", "50", "10")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert corpo["solicitacao_id"] == terceira.pk
    assert "Limite individual insuficiente: R$ 0,00 disponível, R$ 10,00 solicitado" in corpo["detail"]
    assert "Já descontados R$ 100,00" in corpo["detail"]
    assert "esgotado" not in corpo["detail"]


def test_submeter_demanda_pool_zerado_pela_propria_demanda_mostra_valores_e_nao_diz_que_zerou(
    demand_rascunho_rn, solicitante_rn, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.services.budget import BLOQUEIO_SALDO_ZERO
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("100"), valor_comprometido=Decimal("0"),
    )
    *_, terceira = _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "50", "50", "10")

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert corpo["solicitacao_id"] == terceira.pk
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "territorial"
    assert "R$ 0,00 disponível, R$ 10,00 solicitado" in corpo["detail"]
    assert BLOQUEIO_SALDO_ZERO not in corpo["detail"]
    # O pool tem R$ 100 livres no banco: só não cobre esta demanda inteira.
    assert "Território esgotado nesta rubrica para este valor" in corpo["detail"]
    assert "Território esgotado nesta rubrica. Acione" not in corpo["detail"]


def test_submeter_demanda_sem_outras_solicitacoes_nao_menciona_desconto(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("500")
    limite_individual_rn.save(update_fields=["valor_limite"])

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_request_rn.demanda, usuario=solicitante_rn)

    assert "Já descontados" not in excinfo.value.como_dict()["detail"]


def test_submeter_demanda_rubricas_diferentes_nao_somam_consumo(
    demand_rascunho_rn, solicitante_rn, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory, BudgetRubricaFactory

    outra = BudgetRubricaFactory(slug="outra-rubrica-sgd")
    DemandIndividualLimitFactory(solicitante=solicitante_rn, rubrica=outra, valor_limite=100)
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=outra, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("100"), valor_comprometido=Decimal("0"),
    )
    limite_individual_rn.valor_limite = Decimal("100")
    limite_individual_rn.save(update_fields=["valor_limite"])
    _solicitacoes_diaria(demand_rascunho_rn, rubrica_diarias, "60")
    _solicitacoes_diaria(demand_rascunho_rn, outra, "60")

    demand_service.submeter_demanda(demand_rascunho_rn, usuario=solicitante_rn)

    demand_rascunho_rn.refresh_from_db()
    assert demand_rascunho_rn.status == "submetida"


def _pre_checagem_aprova_tudo(monkeypatch):
    """Simula o saldo mudando entre a pré-checagem e a reserva sob lock: a
    pré-checagem enxerga saldo, a reserva não."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        balance_service, "verificar_duas_travas", lambda **kwargs: SimpleNamespace(disponivel=True),
    )


def test_submeter_demanda_bloqueio_individual_na_reserva_identifica_trava_e_solicitacao(
    monkeypatch, demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("500")
    limite_individual_rn.save(update_fields=["valor_limite"])
    _pre_checagem_aprova_tudo(monkeypatch)

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_request_rn.demanda, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "individual"
    assert corpo["solicitacao_id"] == demand_request_rn.pk
    assert "Solicitar recurso extra" in corpo["detail"]
    bloqueio = corpo["solicitacoes_bloqueadas"][str(demand_request_rn.pk)]
    assert bloqueio["trava"] == "individual"
    assert bloqueio["acao_sugerida"] == "solicitar_recurso_extra"

    demand_request_rn.demanda.refresh_from_db()
    assert demand_request_rn.demanda.status == "rascunho"
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_submeter_demanda_bloqueio_territorial_na_reserva_identifica_trava_e_solicitacao(
    monkeypatch, demand_request_rn, solicitante_rn, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("500"), valor_comprometido=Decimal("0"),
    )
    _pre_checagem_aprova_tudo(monkeypatch)

    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand_request_rn.demanda, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "territorial"
    assert corpo["solicitacao_id"] == demand_request_rn.pk
    assert "Acione o Articulador Estadual" in corpo["detail"]
    bloqueio = corpo["solicitacoes_bloqueadas"][str(demand_request_rn.pk)]
    assert bloqueio["trava"] == "territorial"
    assert bloqueio["acao_sugerida"] == "acionar_articulador"

    # A reserva individual já tinha sido feita quando a territorial falhou —
    # a transação da submissão desfaz as duas.
    demand_request_rn.demanda.refresh_from_db()
    assert demand_request_rn.demanda.status == "rascunho"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")


def _bloqueio_da_submissao(demand) -> dict:
    with pytest.raises(SaldoInsuficiente) as excinfo:
        demand_service.submeter_demanda(demand, usuario=demand.solicitante)
    return excinfo.value.como_dict()


def test_bloqueio_individual_na_pre_checagem_e_na_reserva_tem_o_mesmo_contrato(
    monkeypatch, demand_request_rn, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("500")
    limite_individual_rn.save(update_fields=["valor_limite"])

    pela_pre_checagem = _bloqueio_da_submissao(demand_request_rn.demanda)
    _pre_checagem_aprova_tudo(monkeypatch)
    pela_reserva = _bloqueio_da_submissao(demand_request_rn.demanda)

    assert pela_pre_checagem == pela_reserva
    assert pela_reserva["code"] == "INSUFFICIENT_BALANCE"
    assert (pela_reserva["disponivel"], pela_reserva["solicitado"]) == ("500.00", "1000.00")


def test_bloqueio_territorial_na_pre_checagem_e_na_reserva_tem_o_mesmo_contrato(
    monkeypatch, demand_request_rn, activity_rn, rubrica_diarias, limite_individual_rn,
):
    from apps.sgp.tests.factories import BudgetAllocationFactory

    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("500"), valor_comprometido=Decimal("0"),
    )

    pela_pre_checagem = _bloqueio_da_submissao(demand_request_rn.demanda)
    _pre_checagem_aprova_tudo(monkeypatch)
    pela_reserva = _bloqueio_da_submissao(demand_request_rn.demanda)

    assert pela_pre_checagem == pela_reserva
    assert pela_reserva["trava"] == "territorial"
    assert (pela_reserva["disponivel"], pela_reserva["solicitado"]) == ("500.00", "1000.00")


def test_reservar_duas_travas_sem_limite_individual_responde_no_contrato_da_pre_checagem(
    demand_request_rn, solicitante_rn, allocation_territorial_rn,
):
    """O limite removido entre a pré-checagem e o lock não pode virar erro 500."""
    with pytest.raises(SaldoInsuficiente) as excinfo:
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    corpo = excinfo.value.como_dict()
    assert corpo["trava"] == "individual"
    assert corpo["disponivel"] == "0.00"
    assert corpo["solicitacao_id"] == demand_request_rn.pk
    assert corpo["detail"].startswith("Nenhum limite individual configurado para você nesta rubrica")
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_reservar_duas_travas_sem_alocacao_territorial_identifica_trava_e_solicitacao(
    demand_request_rn, solicitante_rn, limite_individual_rn,
):
    with pytest.raises(SaldoInsuficiente) as excinfo:
        balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    assert excinfo.value.como_dict()["code"] == "INSUFFICIENT_BALANCE"
    assert excinfo.value.como_dict()["trava"] == "territorial"
    assert excinfo.value.como_dict()["solicitacao_id"] == demand_request_rn.pk


def test_submeter_bloqueado_responde_400_com_code_e_solicitacao_id(
    auth_client_solicitante, demand_request_rn, allocation_territorial_rn, limite_individual_rn,
):
    limite_individual_rn.valor_limite = Decimal("500")
    limite_individual_rn.save(update_fields=["valor_limite"])

    response = auth_client_solicitante.post(f"/api/v1/sgd/demandas/{demand_request_rn.demanda_id}/submeter/")

    assert response.status_code == 400
    corpo = response.json()
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "individual"
    assert corpo["solicitacao_id"] == demand_request_rn.pk
    assert "Solicitar recurso extra" in corpo["detail"]
    assert corpo["solicitacoes_bloqueadas"][str(demand_request_rn.pk)]["trava"] == "individual"


def _campos_diaria_com_dias(*, municipio, dias_a_mais: int) -> dict:
    """`demand_request_rn` é tipo "diaria" — esse tipo sempre recalcula
    valor_estimado a partir das datas (validado.valor_estimado_auto nunca é
    None), então passar `valor_estimado` direto pro service não muda nada
    sozinho: precisa editar os campos que o auto-cálculo usa."""
    from datetime import date, timedelta

    nova_data_fim = date.fromisoformat("2026-06-01") + timedelta(days=dias_a_mais)
    return {
        "beneficiario_nome": "Fulano de Tal", "beneficiario_cpf": "52998224725",
        "beneficiario_cargo": "Técnico", "beneficiario_vinculo": "servidor_ufersa",
        "municipio_destino_id": municipio.pk, "data_inicio": "2026-06-01",
        "data_fim": nova_data_fim.isoformat(),
        "meio_transporte": "rodoviario", "justificativa": "Visita técnica estendida.",
    }


def test_editar_valor_em_devolvida_ajusta_reserva_ativa(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, limite_individual_rn, allocation_territorial_rn,
    municipio_rn,
):
    """Em Devolvida a reserva é mantida (§4.2) — editar o valor de uma
    solicitação com reserva ativa ajusta a reserva na hora, não só o campo."""
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="sgd_valor_diaria_padrao", defaults={"valor": "200", "tipo": TipoConfiguracao.STRING},
    )
    try:
        demand = demand_request_rn.demanda
        demand_service.submeter_demanda(demand, usuario=solicitante_rn)
        workflow_service.executar_transicao(
            demand, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar valor.",
        )

        campos = _campos_diaria_com_dias(municipio=municipio_rn, dias_a_mais=4)
        demand_service.atualizar_solicitacao(demand_request_rn, usuario=solicitante_rn, campos_json=campos)
        novo_valor = demand_request_rn.valor_estimado  # 4 diárias x R$200 — mutado in place pelo service

        limite_individual_rn.refresh_from_db()
        allocation_territorial_rn.refresh_from_db()
        assert limite_individual_rn.valor_comprometido == novo_valor
        assert allocation_territorial_rn.valor_comprometido == novo_valor
    finally:
        cache.delete("system_config:sgd_valor_diaria_padrao")


def test_resubmissao_apos_edicao_nao_bloqueia_a_toa(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, limite_individual_rn, allocation_territorial_rn,
    municipio_rn,
):
    """A solicitação editada em Devolvida já está com a reserva ajustada —
    ressubmeter não deve checar o valor cheio de novo (isso bloquearia à
    toa, já que o saldo já desconta essa própria reserva)."""
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="sgd_valor_diaria_padrao", defaults={"valor": "200", "tipo": TipoConfiguracao.STRING},
    )
    try:
        demand = demand_request_rn.demanda
        demand_service.submeter_demanda(demand, usuario=solicitante_rn)
        workflow_service.executar_transicao(
            demand, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar valor.",
        )

        # Edita pro valor EXATO do limite — sem folga nenhuma pra "pedir de
        # novo". Se a ressubmissão checasse o valor cheio de novo (em vez de
        # pular quem já tem reserva ativa), contaria essa reserva em dobro e
        # bloquearia aqui; com folga o teste passaria mesmo com o bug antigo.
        dias_no_limite = int(limite_individual_rn.valor_limite / Decimal("200"))
        campos = _campos_diaria_com_dias(municipio=municipio_rn, dias_a_mais=dias_no_limite)
        demand_service.atualizar_solicitacao(demand_request_rn, usuario=solicitante_rn, campos_json=campos)
        novo_valor = demand_request_rn.valor_estimado
        assert novo_valor == limite_individual_rn.valor_limite

        demand_service.submeter_demanda(demand, usuario=solicitante_rn)

        demand.refresh_from_db()
        assert demand.status == "submetida"
        limite_individual_rn.refresh_from_db()
        assert limite_individual_rn.valor_comprometido == novo_valor
    finally:
        cache.delete("system_config:sgd_valor_diaria_padrao")


def test_remover_solicitacao_com_reserva_ativa_libera_saldo(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, limite_individual_rn, allocation_territorial_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    workflow_service.executar_transicao(demand, "devolvida", ator=usuario_articulador_rn, justificativa="Remover item.")

    demand_service.remover_solicitacao(demand_request_rn, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_trocar_tipo_com_reserva_ativa_bloqueado(
    demand_request_rn, solicitante_rn, usuario_articulador_rn, limite_individual_rn, allocation_territorial_rn,
):
    """Trocar `tipo` muda a rubrica — o motor de saldo do SGP não suporta
    trocar a alocação de uma reserva em andamento, então isso é rejeitado
    enquanto há reserva ativa; remover e recriar é o caminho suportado."""
    from apps.sgp.tests.factories import BudgetRubricaFactory

    BudgetRubricaFactory(slug="alimentacao-refeicoes")

    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    workflow_service.executar_transicao(demand, "devolvida", ator=usuario_articulador_rn, justificativa="Tipo errado.")

    with pytest.raises(ErroDeDominio):
        demand_service.atualizar_solicitacao(
            demand_request_rn, usuario=solicitante_rn, tipo="alimentacao",
            campos_json={
                "tipo_refeicao": "almoco", "data_horario_servico": "2026-06-01T12:00:00",
                "numero_pessoas": 10,
            },
        )


def test_liberar_apos_ajuste_libera_o_valor_ajustado_nao_o_congelado(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """Depois de um ajuste, `liberar_duas_travas` precisa liberar o valor
    efetivamente reservado agora — não `valor_estimado`, que fica congelado
    no valor original e ficaria dessincronizado do que está em
    `valor_comprometido`."""
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    novo_valor = demand_request_rn.valor_estimado + Decimal("300")
    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=novo_valor, usuario=solicitante_rn,
    )

    balance_service.liberar_duas_travas(
        demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Teste.",
    )

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_autorizar_excedente_rejeita_origem_territorial(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """RF16: remanejamento emergencial só pode vir de saldo estadual ou
    nacional, nunca de outro pool territorial."""
    from apps.core.tests.factories import TerritoryFactory
    from apps.sgp.models.budget import BudgetAllocation
    from apps.sgp.tests.factories import BudgetAllocationFactory

    # Território diferente do de allocation_territorial_rn — mesma
    # combinação (meta, rubrica, nivel, território) já existe naquela
    # fixture, e colidiria com a unique constraint de BudgetAllocation.
    outro_territorio = TerritoryFactory(nome="Território Origem Excedente", estados=["RN"])
    origem_territorial = BudgetAllocationFactory(
        meta=demand_request_rn.demanda.activity.acao.meta, rubrica=demand_request_rn.rubrica,
        nivel=BudgetAllocation.Nivel.TERRITORIAL, territorio=outro_territorio,
        valor_alocado=Decimal("5000"),
    )

    with pytest.raises(ErroDeDominio):
        balance_service.autorizar_excedente(
            demand_request=demand_request_rn, origem_allocation=origem_territorial,
            valor_excedente=Decimal("500"), justificativa="Tentativa inválida.", usuario=solicitante_rn,
        )


@pytest.mark.parametrize(
    ("allocation", "saldo", "esperado"),
    [
        (None, None, "Acione o Articulador Estadual para alocar saldo ao território."),
        (object(), Decimal("0"), "Território esgotado nesta rubrica. Acione o Articulador Estadual."),
        (object(), Decimal("500"), "Território esgotado nesta rubrica para este valor. Acione o Articulador Estadual."),
        (object(), None, "Território esgotado nesta rubrica para este valor. Acione o Articulador Estadual."),
    ],
)
def test_orientacao_territorial_por_situacao_do_pool(allocation, saldo, esperado):
    assert orcamento_service.orientacao_territorial(allocation=allocation, saldo=saldo) == esperado


# ── Estado da reserva materializado na solicitação ───────────────────────────

def _confere_comprometido(limite) -> None:
    """O invariante do limite individual: o comprometido é a soma das reservas ativas."""
    limite.refresh_from_db()
    reservado = DemandRequest.objects.filter(
        RESERVA_ATIVA, demanda__solicitante=limite.solicitante, rubrica=limite.rubrica,
    ).aggregate(total=Sum("valor_reservado"))["total"] or Decimal("0")
    assert limite.valor_comprometido == reservado


@pytest.fixture
def diaria_a_200(db):
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="sgd_valor_diaria_padrao", defaults={"valor": "200", "tipo": TipoConfiguracao.STRING},
    )
    yield
    cache.delete("system_config:sgd_valor_diaria_padrao")


@pytest.mark.parametrize(("dias", "valor_editado"), [(2, Decimal("400")), (7, Decimal("1400"))])
def test_ciclo_da_reserva_mantem_o_comprometido_igual_as_reservas_ativas(
    dias, valor_editado, diaria_a_200, demand_request_rn, solicitante_rn, usuario_articulador_rn,
    limite_individual_rn, allocation_territorial_rn, activity_rn, rubrica_diarias, municipio_rn,
):
    outra = DemandRequestFactory(
        demanda=DemandFactory(activity=activity_rn, solicitante=solicitante_rn), tipo="diaria",
        rubrica=rubrica_diarias, valor_estimado=Decimal("300"),
    )
    balance_service.reservar_duas_travas(demand_request=outra, usuario=solicitante_rn)
    demand = demand_request_rn.demanda

    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand_request_rn.refresh_from_db()
    assert (demand_request_rn.valor_reservado, demand_request_rn.reserva_ativa) == (Decimal("1000"), True)
    _confere_comprometido(limite_individual_rn)

    workflow_service.executar_transicao(
        demand, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar valor.",
    )
    _confere_comprometido(limite_individual_rn)

    campos = _campos_diaria_com_dias(municipio=municipio_rn, dias_a_mais=dias)
    demand_service.atualizar_solicitacao(demand_request_rn, usuario=solicitante_rn, campos_json=campos)
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == valor_editado
    _confere_comprometido(limite_individual_rn)

    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == valor_editado
    _confere_comprometido(limite_individual_rn)

    balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Teste.")
    demand_request_rn.refresh_from_db()
    assert (demand_request_rn.valor_reservado, demand_request_rn.reserva_ativa) == (Decimal("0"), False)
    _confere_comprometido(limite_individual_rn)

    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == demand_request_rn.valor_estimado == valor_editado
    _confere_comprometido(limite_individual_rn)


def test_reservar_duas_vezes_nao_reserva_de_novo_mesmo_com_instancia_desatualizada(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    desatualizada = DemandRequest.objects.get(pk=demand_request_rn.pk)
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    balance_service.reservar_duas_travas(demand_request=desatualizada, usuario=solicitante_rn)

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    _confere_comprometido(limite_individual_rn)


def test_executar_tira_do_comprometido_o_valor_reservado_e_e_idempotente(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """Sem `valor_autorizado`, o código antigo tirava o `valor_estimado` (1.000)
    de um comprometido de 800 e deixava o limite negativo."""
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.ajustar_duas_travas(
        demand_request=demand_request_rn, novo_valor=Decimal("800"), usuario=solicitante_rn,
    )

    for _ in range(2):
        balance_service.executar_duas_travas(
            demand_request=demand_request_rn, valor_pago=Decimal("750"), usuario=solicitante_rn,
        )

    demand_request_rn.refresh_from_db()
    assert (demand_request_rn.valor_reservado, demand_request_rn.valor_executado) == (Decimal("800"), Decimal("750"))
    assert demand_request_rn.reserva_ativa is False
    limite_individual_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado) == (
        Decimal("0"), Decimal("750"),
    )
    _confere_comprometido(limite_individual_rn)


def test_liberar_depois_de_executar_nao_devolve_nada(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    balance_service.executar_duas_travas(
        demand_request=demand_request_rn, valor_pago=Decimal("1000"), usuario=solicitante_rn,
    )

    balance_service.liberar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn, motivo="Teste.")

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_executado == Decimal("1000")


def test_ajustar_sem_reserva_ativa_e_regra_de_negocio(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    with pytest.raises(RegraDeNegocio):
        balance_service.ajustar_duas_travas(
            demand_request=demand_request_rn, novo_valor=Decimal("800"), usuario=solicitante_rn,
        )

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("0")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("valor_reservado", Decimal("-1")), ("valor_executado", Decimal("-1"))],
)
def test_estado_da_reserva_nao_aceita_valor_negativo(demand_request_rn, campo, valor):
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandRequest.objects.filter(pk=demand_request_rn.pk).update(**{campo: valor})


@pytest.mark.parametrize("campo", ["valor_comprometido", "valor_executado"])
def test_limite_individual_nao_aceita_saldo_negativo(limite_individual_rn, campo):
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(**{campo: Decimal("-1")})


@pytest.fixture
def demanda_com_duas_rubricas(demand_request_rn, solicitante_rn, activity_rn, allocation_territorial_rn, limite_individual_rn):
    from apps.sgp.tests.factories import BudgetAllocationFactory, BudgetRubricaFactory

    outra = BudgetRubricaFactory(slug="rubrica-ordem-de-lock")
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=outra, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("10000"),
    )
    DemandIndividualLimitFactory(solicitante=solicitante_rn, rubrica=outra, valor_limite=Decimal("5000"))
    DemandRequestFactory(demanda=demand_request_rn.demanda, rubrica=outra, valor_estimado=Decimal("200"))
    return demand_request_rn.demanda


def _ordem(consultas):
    sqls = [q["sql"] for q in consultas]
    travas_de_saldo = [
        i for i, sql in enumerate(sqls)
        if "FOR UPDATE" in sql and ('"sgd_demandindividuallimit"' in sql or '"sgp_budgetallocation"' in sql)
    ]
    demanda = [
        i for i, sql in enumerate(sqls)
        if sql.startswith('UPDATE "sgd_demand" ') or ("FOR UPDATE" in sql and 'FROM "sgd_demand" ' in sql)
    ]
    gravacoes_da_reserva = [i for i, sql in enumerate(sqls) if sql.startswith('UPDATE "sgd_demandrequest"')]
    return travas_de_saldo, demanda, gravacoes_da_reserva


def test_submissao_grava_o_estado_da_reserva_depois_do_saldo_e_da_demand(demanda_com_duas_rubricas, solicitante_rn):
    """Gravar a solicitação logo depois do seu pool a deixaria travada antes do limite
    da rubrica seguinte e da Demand; a decisão de recurso extra trava Demand e depois
    as solicitações, e as duas fechariam um ciclo."""
    with CaptureQueriesContext(connection) as consultas:
        demand_service.submeter_demanda(demanda_com_duas_rubricas, usuario=solicitante_rn)

    travas_de_saldo, demanda, gravacoes_da_reserva = _ordem(consultas)
    assert len(gravacoes_da_reserva) == 2
    assert max(travas_de_saldo) < min(demanda) < min(gravacoes_da_reserva)
    assert all(s.reserva_ativa for s in demanda_com_duas_rubricas.solicitacoes.all())
    _confere_comprometido(DemandIndividualLimit.objects.get(solicitante=solicitante_rn, rubrica__slug="diarias"))


def test_cancelamento_grava_o_estado_da_reserva_depois_do_saldo_e_da_demand(demanda_com_duas_rubricas, solicitante_rn):
    demand_service.submeter_demanda(demanda_com_duas_rubricas, usuario=solicitante_rn)

    with CaptureQueriesContext(connection) as consultas:
        demand_service.cancelar_demanda(demanda_com_duas_rubricas, usuario=solicitante_rn)

    travas_de_saldo, demanda, gravacoes_da_reserva = _ordem(consultas)
    assert len(gravacoes_da_reserva) == 2
    assert max(travas_de_saldo) < min(demanda) < min(gravacoes_da_reserva)
    assert not any(s.reserva_ativa for s in demanda_com_duas_rubricas.solicitacoes.all())
    for limite in DemandIndividualLimit.objects.filter(solicitante=solicitante_rn):
        assert limite.valor_comprometido == Decimal("0")


def test_autorizacao_grava_as_solicitacoes_depois_do_saldo_e_da_demand(
    demanda_com_duas_rubricas, solicitante_rn, usuario_ugp,
):
    """Ajustar e gravar uma rubrica antes de travar o limite da seguinte deixaria a
    solicitação travada fora da ordem de lock."""
    demand_service.submeter_demanda(demanda_com_duas_rubricas, usuario=solicitante_rn)
    demanda_com_duas_rubricas.status = "pre_autorizada"
    demanda_com_duas_rubricas.save(update_fields=["status"])
    ajustes = {s.pk: s.valor_estimado - Decimal("50") for s in demanda_com_duas_rubricas.solicitacoes.all()}

    with CaptureQueriesContext(connection) as consultas:
        workflow_service.executar_transicao(
            demanda_com_duas_rubricas, "autorizada", ator=usuario_ugp, ajustes=ajustes,
        )

    travas_de_saldo, demanda, gravacoes_da_reserva = _ordem(consultas)
    assert len(gravacoes_da_reserva) == 2
    assert max(travas_de_saldo) < min(demanda) < min(gravacoes_da_reserva)
    assert dict(demanda_com_duas_rubricas.solicitacoes.values_list("pk", "valor_autorizado")) == ajustes
    assert dict(demanda_com_duas_rubricas.solicitacoes.values_list("pk", "valor_reservado")) == ajustes


def test_conclusao_grava_as_solicitacoes_depois_do_saldo_e_da_demand(
    demanda_com_duas_rubricas, solicitante_rn, usuario_fgd,
):
    demand_service.submeter_demanda(demanda_com_duas_rubricas, usuario=solicitante_rn)
    demanda_com_duas_rubricas.status = "em_atendimento"
    demanda_com_duas_rubricas.save(update_fields=["status"])
    pagos = {s.pk: s.valor_estimado for s in demanda_com_duas_rubricas.solicitacoes.all()}

    with CaptureQueriesContext(connection) as consultas:
        workflow_service.executar_transicao(
            demanda_com_duas_rubricas, "concluida", ator=usuario_fgd, valores_pagos=pagos,
        )

    travas_de_saldo, demanda, gravacoes_da_reserva = _ordem(consultas)
    assert len(gravacoes_da_reserva) == 2
    assert max(travas_de_saldo) < min(demanda) < min(gravacoes_da_reserva)
    assert dict(demanda_com_duas_rubricas.solicitacoes.values_list("pk", "valor_pago")) == pagos
    assert dict(demanda_com_duas_rubricas.solicitacoes.values_list("pk", "valor_executado")) == pagos


def test_recusa_libera_e_grava_o_estado_da_reserva(
    demand_request_rn, solicitante_rn, usuario_ugp, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])

    workflow_service.executar_transicao(demand, "recusada", ator=usuario_ugp, justificativa="Sem prioridade.")

    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == Decimal("0")
    _confere_comprometido(limite_individual_rn)
