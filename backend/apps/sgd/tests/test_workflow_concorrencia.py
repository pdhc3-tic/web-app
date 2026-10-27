"""Transições concorrentes seguem a ordem de lock (limite → alocação → Demand →
DemandRequest): quem espera não segura a Demand, e quem chega depois relê o
status e as solicitações sob o lock."""
from decimal import Decimal

import pytest
from django.db import connection

from apps.sgd.exceptions import ErroDeDominio, TransicaoInvalida
from apps.sgd.models import Demand, DemandIndividualLimit, DemandRequest
from apps.sgd.services import demand as demand_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.arlo_import import processar_importacao
from apps.sgd.tests.concorrencia import intercalar

# Fixtures e helpers compartilhados com a suíte de integração Arlo.
from apps.sgd.tests.test_arlo_integration import (  # noqa: F401
    _importar, _linha, _nova_demanda_autorizada, storage_local,
)
from apps.sgp.models import GlosaRisk


@pytest.fixture
def autorizada(demand_request_rn, solicitante_rn, usuario_articulador_rn, usuario_ugp,
               allocation_territorial_rn, limite_individual_rn):
    demand = demand_request_rn.demanda
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    workflow_service.executar_transicao(demand, "pre_autorizada", ator=usuario_articulador_rn)
    workflow_service.executar_transicao(demand, "autorizada", ator=usuario_ugp)
    return Demand.objects.get(pk=demand.pk)


def _travar_limite(demand):
    solicitacao = demand.solicitacoes.get()
    DemandIndividualLimit.objects.select_for_update().get(solicitante=demand.solicitante, rubrica=solicitacao.rubrica)


def _saldo(limite, allocation):
    limite.refresh_from_db()
    allocation.refresh_from_db()
    return (
        limite.valor_comprometido, limite.valor_executado,
        allocation.valor_comprometido, allocation.valor_executado,
    )


@pytest.mark.django_db(transaction=True)
def test_importacao_arlo_espera_o_limite_sem_segurar_a_demanda_do_cancelamento(
    autorizada, usuario_ugp, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    """O cancelamento trava o limite e, depois, a Demand. A linha do Arlo espera o
    limite sem ter travado a Demand; travando-a antes, as duas fechariam um ciclo."""
    importacao = _importar([_linha(autorizada.solicitacoes.get())], usuario_fgd)

    def cancelar(pausa):
        _travar_limite(autorizada)
        pausa()
        demand_service.cancelar_demanda(
            Demand.objects.get(pk=autorizada.pk), usuario=usuario_ugp, motivo="Evento suspenso.",
        )

    _, erros = intercalar(cancelar, lambda: processar_importacao(importacao))

    assert erros == {}
    autorizada.refresh_from_db()
    assert autorizada.status == "cancelada"
    importacao.refresh_from_db()
    assert (importacao.registros_ok, len(importacao.erros_json)) == (0, 1)
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (0, 0, 0, 0)
    assert not GlosaRisk.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_importacao_arlo_e_conclusao_pela_tela_pagam_uma_vez_so(
    autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    workflow_service.executar_transicao(autorizada, "em_atendimento", ator=usuario_fgd)
    solicitacao = autorizada.solicitacoes.get()
    importacao = _importar([_linha(solicitacao, valor="1000,00")], usuario_fgd)

    def concluir(pausa):
        _travar_limite(autorizada)
        pausa()
        workflow_service.executar_transicao(
            Demand.objects.get(pk=autorizada.pk), "concluida", ator=usuario_fgd,
            valores_pagos={solicitacao.pk: Decimal("900")},
        )

    _, erros = intercalar(concluir, lambda: processar_importacao(importacao))

    assert erros == {}
    solicitacao.refresh_from_db()
    assert solicitacao.valor_pago == Decimal("900.00")
    importacao.refresh_from_db()
    assert (importacao.registros_ok, len(importacao.erros_json)) == (0, 1)
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (0, Decimal("900.00"), 0, Decimal("900.00"))


@pytest.mark.django_db(transaction=True)
def test_decisoes_simultaneas_so_a_primeira_vale(usuario_articulador_rn, activity_rn):
    from apps.sgd.tests.factories import DemandFactory

    demand = DemandFactory(activity=activity_rn, status="submetida")
    lida_pela_devolucao = Demand.objects.get(pk=demand.pk)

    def pre_autorizar(pausa):
        workflow_service.executar_transicao(demand, "pre_autorizada", ator=usuario_articulador_rn)
        pausa()

    _, erros = intercalar(
        pre_autorizar,
        lambda: workflow_service.executar_transicao(
            lida_pela_devolucao, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar.",
        ),
    )

    assert set(erros) == {"espera"}
    assert isinstance(erros["espera"], TransicaoInvalida)
    demand.refresh_from_db()
    assert demand.status == "pre_autorizada"
    assert list(demand.etapas.values_list("acao", flat=True)) == ["aprovado"]


@pytest.mark.django_db(transaction=True)
def test_submissao_recusada_quando_a_solicitacao_e_removida_enquanto_reserva(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    """A remoção trava a Demand antes de apagar a solicitação; a submissão, que já
    tinha reservado o saldo dela, confere as solicitações sob o mesmo lock."""
    demand = demand_request_rn.demanda

    def remover(pausa):
        demand_service.remover_solicitacao(DemandRequest.objects.get(pk=demand_request_rn.pk), usuario=solicitante_rn)
        pausa()

    _, erros = intercalar(
        remover, lambda: demand_service.submeter_demanda(Demand.objects.get(pk=demand.pk), usuario=solicitante_rn),
    )

    assert set(erros) == {"espera"}
    assert isinstance(erros["espera"], TransicaoInvalida)
    demand.refresh_from_db()
    assert demand.status == "rascunho"
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (0, 0, 0, 0)


@pytest.mark.django_db(transaction=True)
def test_remocao_recusada_quando_a_demanda_e_submetida_enquanto_espera(
    demand_request_rn, solicitante_rn, limite_individual_rn, allocation_territorial_rn,
):
    demand = demand_request_rn.demanda

    def submeter(pausa):
        demand_service.submeter_demanda(Demand.objects.get(pk=demand.pk), usuario=solicitante_rn)
        pausa()

    _, erros = intercalar(
        submeter,
        lambda: demand_service.remover_solicitacao(
            DemandRequest.objects.get(pk=demand_request_rn.pk), usuario=solicitante_rn,
        ),
    )

    assert set(erros) == {"espera"}
    assert isinstance(erros["espera"], ErroDeDominio)
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == Decimal("1000")
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (Decimal("1000"), 0, Decimal("1000"), 0)


@pytest.mark.django_db(transaction=True)
def test_cancelamento_pela_task_desfeito_quando_a_fgd_inicia_o_atendimento(
    autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    lida_pela_task = Demand.objects.get(pk=autorizada.pk)

    def atender(pausa):
        workflow_service.executar_transicao(
            Demand.objects.get(pk=autorizada.pk), "em_atendimento", ator=usuario_fgd,
        )
        pausa()

    _, erros = intercalar(
        atender, lambda: workflow_service.cancelar_pelo_sistema([lida_pela_task], motivo="Atividade cancelada."),
    )

    assert set(erros) == {"espera"}
    assert isinstance(erros["espera"], TransicaoInvalida)
    autorizada.refresh_from_db()
    assert autorizada.status == "em_atendimento"
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (Decimal("1000"), 0, Decimal("1000"), 0)


@pytest.mark.django_db(transaction=True)
def test_edicoes_simultaneas_em_devolvida_deixam_reserva_e_saldo_iguais(
    solicitante_rn, usuario_articulador_rn, activity_rn, rubrica_diarias,
    limite_individual_rn, allocation_territorial_rn,
):
    """A segunda edição leu a reserva antes da primeira ajustá-la. Ela relê a reserva
    com o limite travado e ajusta a partir do valor real, sem gravar o antigo."""
    from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory

    demand = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="rascunho")
    solicitacao = DemandRequestFactory(
        demanda=demand, rubrica=rubrica_diarias, tipo="grafico", valor_estimado=Decimal("1000"),
        campos_json={
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "x", "prazo_entrega": "2026-12-01",
        },
    )
    demand_service.submeter_demanda(demand, usuario=solicitante_rn)
    workflow_service.executar_transicao(demand, "devolvida", ator=usuario_articulador_rn, justificativa="Ajustar.")
    lida_pela_segunda = DemandRequest.objects.get(pk=solicitacao.pk)

    def primeira(pausa):
        demand_service.atualizar_solicitacao(
            DemandRequest.objects.get(pk=solicitacao.pk), usuario=solicitante_rn, valor_estimado=Decimal("1200"),
        )
        pausa()

    _, erros = intercalar(
        primeira,
        lambda: demand_service.atualizar_solicitacao(
            lida_pela_segunda, usuario=solicitante_rn, valor_estimado=Decimal("1000"),
        ),
    )

    assert erros == {}
    solicitacao.refresh_from_db()
    assert solicitacao.valor_estimado == solicitacao.valor_reservado == Decimal("1000")
    assert _saldo(limite_individual_rn, allocation_territorial_rn) == (Decimal("1000"), 0, Decimal("1000"), 0)


@pytest.mark.django_db(transaction=True)
def test_cancelamento_pela_task_recusado_quando_a_solicitacao_muda_de_rubrica(
    demand_request_rn, solicitante_rn, activity_rn, rubrica_diarias, allocation_territorial_rn, limite_individual_rn,
):
    """A task leu a solicitação na rubrica r1 e espera o limite de r1. Nesse meio, ela
    passa para r2 e a demanda é submetida, reservando em r2. A liberação, que trava o
    limite pela rubrica lida, tiraria a reserva de r1; a conferência sob o lock da
    Demand desfaz tudo."""
    from apps.sgd.services import balance as balance_service
    from apps.sgd.tests.factories import DemandFactory, DemandIndividualLimitFactory, DemandRequestFactory
    from apps.sgp.tests.factories import BudgetAllocationFactory, BudgetRubricaFactory

    outra_rubrica = BudgetRubricaFactory(slug="rubrica-troca-durante-o-cancelamento")
    limite_r2 = DemandIndividualLimitFactory(solicitante=solicitante_rn, rubrica=outra_rubrica, valor_limite=5_000)
    BudgetAllocationFactory(
        meta=activity_rn.acao.meta, rubrica=outra_rubrica, territorio=activity_rn.municipio.territory,
        valor_alocado=10_000,
    )
    # Outra reserva em r1, para a liberação indevida não esbarrar no comprometido negativo.
    vizinha = DemandRequestFactory(
        demanda=DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida"),
        rubrica=rubrica_diarias, valor_estimado=Decimal("1000"),
    )
    balance_service.reservar_duas_travas(demand_request=vizinha, usuario=solicitante_rn)
    demand = demand_request_rn.demanda

    def trocar_e_submeter(pausa):
        DemandIndividualLimit.objects.select_for_update().get(pk=limite_individual_rn.pk)
        pausa()
        DemandRequest.objects.filter(pk=demand_request_rn.pk).update(rubrica=outra_rubrica)
        demand_service.submeter_demanda(Demand.objects.get(pk=demand.pk), usuario=solicitante_rn)

    _, erros = intercalar(
        trocar_e_submeter,
        lambda: workflow_service.cancelar_pelo_sistema(
            [Demand.objects.get(pk=demand.pk)], motivo="Atividade cancelada.",
        ),
    )

    assert set(erros) == {"espera"}
    assert isinstance(erros["espera"], TransicaoInvalida)
    demand.refresh_from_db()
    assert demand.status == "submetida"
    limite_individual_rn.refresh_from_db()
    limite_r2.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_r2.valor_comprometido) == (Decimal("1000"), Decimal("1000"))


@pytest.mark.django_db(transaction=True)
def test_task_da_importacao_abre_uma_transacao_por_linha_com_o_papel_da_sessao(
    monkeypatch, demand_request_rn, solicitante_rn, activity_rn, rubrica_diarias, usuario_fgd,
    allocation_territorial_rn, limite_individual_rn,
):
    """Com o arquivo numa transação só, a linha anterior seguraria alocação e Demand
    enquanto a seguinte trava o limite de outro solicitante, fora da ordem de lock."""
    from apps.sgd import tasks as sgd_tasks
    from apps.sgd.services import arlo_import
    from apps.sgd.tests.test_arlo_integration import _autorizar

    primeira = _autorizar(demand_request_rn, solicitante_rn)
    segunda = _nova_demanda_autorizada(activity_rn, solicitante_rn, rubrica_diarias)
    original = arlo_import._processar_linha
    vistas = []

    def espiar(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.user_role', true)")
            papel = cursor.fetchone()[0]
        vistas.append((list(connection.savepoint_ids), papel))
        return original(*args, **kwargs)

    monkeypatch.setattr(arlo_import, "_processar_linha", espiar)
    importacao = _importar([_linha(primeira), _linha(segunda, valor="500,00", processo="PROC-2")], usuario_fgd)

    assert sgd_tasks.process_arlo_import(importacao.pk) == 2
    assert vistas == [([], "super-admin"), ([], "super-admin")]
