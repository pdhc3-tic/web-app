from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.tests.factories import UserFactory
from apps.sgd.exceptions import RegraDeNegocio, SaldoInsuficiente
from apps.sgd.services import orcamento as orcamento_service
from apps.sgp.tests.factories import BudgetAllocationFactory, WorkPlanMetaFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def alocacao_de_outra_meta(activity_rn, rubrica_diarias):
    """Mesma rubrica e território, Meta diferente: só a Meta da atividade
    distingue as duas alocações."""
    return BudgetAllocationFactory(
        meta=WorkPlanMetaFactory(), rubrica=rubrica_diarias, territorio=activity_rn.municipio.territory,
        valor_alocado=Decimal("1"),
    )


def test_consultar_pool_resolve_a_meta_pela_atividade_da_demanda(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, alocacao_de_outra_meta,
):
    check = orcamento_service.consultar_pool(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"), demand_request=demand_request_rn,
    )

    assert check.disponivel is True
    assert check.allocation == allocation_territorial_rn


def test_consultar_pool_sem_solicitacao_resolve_a_meta_pela_atividade(
    activity_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, alocacao_de_outra_meta,
):
    check = orcamento_service.consultar_pool(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"), activity=activity_rn,
    )

    assert check.allocation == allocation_territorial_rn


def test_consultar_pool_sem_atividade_e_regra_de_negocio(solicitante_rn, rubrica_diarias):
    with pytest.raises(RegraDeNegocio):
        orcamento_service.consultar_pool(solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"))


def test_consultar_pool_insuficiente_traz_a_mensagem_em_reais(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    check = orcamento_service.consultar_pool(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("12000"), demand_request=demand_request_rn,
    )

    assert check.disponivel is False
    assert "R$ 10.000,00 disponível, R$ 12.000,00 solicitado" in check.motivo_bloqueio
    assert "Acione o Articulador Estadual" in check.motivo_bloqueio


def test_reservar_pool_insuficiente_vira_saldo_insuficiente_territorial(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    with pytest.raises(SaldoInsuficiente) as excinfo:
        orcamento_service.reservar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("12000"),
            demand_request=demand_request_rn, usuario=solicitante_rn,
        )

    corpo = excinfo.value.como_dict()
    assert corpo["trava"] == "territorial"
    assert corpo["rubrica"] == "diarias"
    assert corpo["disponivel"] == "10000.00"
    assert corpo["solicitado"] == "12000.00"
    assert corpo["acao_sugerida"] == "acionar_articulador"
    assert corpo["solicitacao_id"] == demand_request_rn.pk
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_reservar_pool_sem_alocacao_vira_saldo_insuficiente_territorial(
    demand_request_rn, solicitante_rn, rubrica_diarias,
):
    with pytest.raises(SaldoInsuficiente) as excinfo:
        orcamento_service.reservar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"),
            demand_request=demand_request_rn, usuario=solicitante_rn,
        )

    assert excinfo.value.trava == "territorial"
    assert excinfo.value.disponivel == Decimal("0")
    assert excinfo.value.mensagem.startswith(
        "Nenhuma alocação orçamentária territorial encontrada: R$ 0,00 disponível, R$ 100,00 solicitado."
    )


def test_reservar_pool_reserva_na_alocacao_da_meta_da_atividade(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn, alocacao_de_outra_meta,
):
    movimento = orcamento_service.reservar_pool(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("300"),
        demand_request=demand_request_rn, usuario=solicitante_rn,
    )

    assert movimento.allocation == allocation_territorial_rn
    assert movimento.comprometido_antes == Decimal("0")
    allocation_territorial_rn.refresh_from_db()
    alocacao_de_outra_meta.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("300")
    assert alocacao_de_outra_meta.valor_comprometido == Decimal("0")


def test_executar_pool_sem_reserva_e_regra_de_negocio(demand_request_rn, solicitante_rn, rubrica_diarias):
    with pytest.raises(RegraDeNegocio):
        orcamento_service.executar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"),
            demand_request=demand_request_rn, usuario=solicitante_rn,
        )


def test_liberar_pool_sem_reserva_nao_faz_nada(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    orcamento_service.liberar_pool(
        solicitante=solicitante_rn, rubrica=rubrica_diarias, demand_request=demand_request_rn,
        usuario=solicitante_rn, motivo="Rascunho cancelado.",
    )

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_localizar_pool_sem_alocacao_e_regra_de_negocio(demand_request_rn, solicitante_rn, rubrica_diarias):
    with pytest.raises(RegraDeNegocio):
        orcamento_service.localizar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, demand_request=demand_request_rn,
        )


def test_remanejar_sem_saldo_na_origem_recusa_em_reais_sem_mover_nada(
    activity_rn, rubrica_diarias, allocation_territorial_rn, solicitante_rn,
):
    from apps.sgp.models import BudgetAllocation, BudgetTransaction

    origem = BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        territorio=None, estado=activity_rn.municipio.state,
        valor_alocado=Decimal("1500"), valor_comprometido=Decimal("200"),
    )

    with pytest.raises(RegraDeNegocio) as excinfo:
        orcamento_service.remanejar(
            origem=origem, destino=allocation_territorial_rn, valor=Decimal("2000"),
            usuario=solicitante_rn, justificativa="Excedente.",
        )

    assert excinfo.value.campo == "valor"
    assert excinfo.value.mensagem == "Saldo insuficiente na origem: R$ 1.300,00 disponível, R$ 2.000,00 solicitado."
    assert not BudgetTransaction.objects.filter(tipo=BudgetTransaction.Tipo.REMANEJAMENTO).exists()
    origem.refresh_from_db()
    assert origem.valor_alocado == Decimal("1500")


def test_consultar_pool_com_rubrica_desativada_usa_excecao_de_dominio(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    rubrica_diarias.ativo = False
    rubrica_diarias.save(update_fields=["ativo"])

    with pytest.raises(RegraDeNegocio) as excinfo:
        orcamento_service.consultar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"),
            demand_request=demand_request_rn,
        )

    assert excinfo.value.campo == "rubrica"
    assert excinfo.value.mensagem == "Rubrica 'diarias' não existe ou está inativa."


def test_reservar_pool_com_rubrica_desativada_usa_excecao_de_dominio(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    rubrica_diarias.ativo = False
    rubrica_diarias.save(update_fields=["ativo"])

    with pytest.raises(RegraDeNegocio) as excinfo:
        orcamento_service.reservar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"),
            demand_request=demand_request_rn, usuario=solicitante_rn,
        )

    assert excinfo.value.campo == "rubrica"
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("0")


def test_remanejar_para_a_mesma_alocacao_e_regra_de_negocio(allocation_territorial_rn, solicitante_rn):
    from apps.sgp.models import BudgetTransaction

    with pytest.raises(RegraDeNegocio) as excinfo:
        orcamento_service.remanejar(
            origem=allocation_territorial_rn, destino=allocation_territorial_rn, valor=Decimal("100"),
            usuario=solicitante_rn, justificativa="Excedente.",
        )

    assert excinfo.value.campo == "destino_allocation"
    assert excinfo.value.mensagem == "Origem e destino não podem ser a mesma alocação."
    assert not BudgetTransaction.objects.filter(tipo=BudgetTransaction.Tipo.REMANEJAMENTO).exists()


def test_remanejamento_com_meta_incompativel_devolve_business_rule(
    auth_client_ugp, demand_request_rn, allocation_territorial_rn, rubrica_diarias,
):
    """Origem com saldo e a mesma rubrica, só a Meta difere: a recusa é a
    incompatibilidade, não falta de saldo nem de permissão."""
    origem = BudgetAllocationFactory(
        meta=WorkPlanMetaFactory(), rubrica=rubrica_diarias,
        nivel="nacional", territorio=None, valor_alocado=Decimal("1000"),
    )

    response = auth_client_ugp.post(
        f"/api/v1/sgd/demandas/{demand_request_rn.demanda_id}/autorizar-excedente/",
        {
            "demand_request_id": demand_request_rn.pk,
            "origem_allocation_id": origem.pk,
            "valor_excedente": "100.00",
            "justificativa": "Teste do contrato da porta",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data == {
        "destino_allocation": ["Origem e destino devem ser da mesma Meta e Rubrica."],
        "code": "BUSINESS_RULE",
    }


def test_consultar_pool_com_solicitante_sem_nivel_nega_com_a_excecao_do_django(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    solicitante_rn.profiles.update(territorio=None)

    with pytest.raises(PermissionDenied) as excinfo:
        orcamento_service.consultar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, valor=Decimal("100"),
            demand_request=demand_request_rn,
        )

    assert str(excinfo.value).startswith("Perfil sem estado/território específico")


def test_localizar_pool_com_solicitante_sem_nivel_e_regra_de_negocio(
    demand_request_rn, solicitante_rn, rubrica_diarias, allocation_territorial_rn,
):
    solicitante_rn.profiles.update(territorio=None)

    with pytest.raises(RegraDeNegocio) as excinfo:
        orcamento_service.localizar_pool(
            solicitante=solicitante_rn, rubrica=rubrica_diarias, demand_request=demand_request_rn,
        )

    assert excinfo.value.mensagem.startswith("Não há como conferir o pool territorial do solicitante.")


def test_painel_para_usuario_sem_acesso_nega_com_a_excecao_do_django():
    with pytest.raises(PermissionDenied) as excinfo:
        orcamento_service.painel_orcamento_para_usuario(UserFactory())

    assert str(excinfo.value) == "Você não tem acesso ao orçamento do SGP."
