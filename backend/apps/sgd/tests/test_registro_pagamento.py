"""Pagamento pela conclusão da FGD e pela importação do Arlo: mesma política,
mesmo resultado."""
from decimal import Decimal

import pytest
from django.db.models import Q

from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models import Demand, DemandRequest
from apps.sgd.services import demand as demand_service
from apps.sgd.services import workflow as workflow_service
from apps.sgd.services.arlo_import import processar_importacao
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory

# Fixtures e helpers compartilhados com a suíte de integração Arlo.
from apps.sgd.tests.test_arlo_integration import _importar, _linha, storage_local  # noqa: F401
from apps.sgp.models import GlosaRisk

pytestmark = pytest.mark.django_db

CAMINHOS = ["tela", "arlo"]


@pytest.fixture
def aprovadores(usuario_articulador_rn, usuario_ugp, usuario_fgd):
    return {"articulador": usuario_articulador_rn, "ugp": usuario_ugp, "fgd": usuario_fgd}


def _autorizar_pelo_fluxo(demand, solicitante, aprovadores):
    demand_service.submeter_demanda(demand, usuario=solicitante)
    workflow_service.executar_transicao(demand, "pre_autorizada", ator=aprovadores["articulador"])
    workflow_service.executar_transicao(demand, "autorizada", ator=aprovadores["ugp"])
    return Demand.objects.get(pk=demand.pk)


@pytest.fixture
def autorizada(demand_request_rn, solicitante_rn, aprovadores, allocation_territorial_rn, limite_individual_rn):
    return _autorizar_pelo_fluxo(demand_request_rn.demanda, solicitante_rn, aprovadores)


def _outra_autorizada(activity, solicitante, rubrica, aprovadores):
    demand = DemandFactory(activity=activity, solicitante=solicitante, status="rascunho")
    DemandRequestFactory(demanda=demand, tipo="diaria", rubrica=rubrica, valor_estimado=Decimal("1000"))
    return _autorizar_pelo_fluxo(demand, solicitante, aprovadores)


def _pagar(caminho, demand, valor: Decimal, usuario_fgd):
    solicitacao = demand.solicitacoes.get()
    if caminho == "tela":
        workflow_service.executar_transicao(demand, "em_atendimento", ator=usuario_fgd)
        workflow_service.executar_transicao(
            demand, "concluida", ator=usuario_fgd, valores_pagos={solicitacao.pk: valor},
        )
    else:
        importacao = processar_importacao(
            _importar([_linha(solicitacao, valor=f"{valor:.2f}".replace(".", ","))], usuario_fgd),
        )
        assert importacao.erros_json == []
    solicitacao.refresh_from_db()
    return solicitacao


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_pago_acima_do_autorizado_conclui_executa_o_autorizado_e_registra_glosa(
    caminho, autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    solicitacao = _pagar(caminho, autorizada, Decimal("1200.00"), usuario_fgd)

    autorizada.refresh_from_db()
    assert autorizada.status == "concluida"
    assert (solicitacao.valor_pago, solicitacao.valor_executado) == (Decimal("1200.00"), Decimal("1000.00"))
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado) == (
        Decimal("0"), Decimal("1000.00"),
    )
    assert (allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado) == (
        Decimal("0"), Decimal("1000.00"),
    )
    glosa = GlosaRisk.objects.get()
    assert (glosa.valor_autorizado, glosa.valor_pago, glosa.excedente) == (
        Decimal("1000.00"), Decimal("1200.00"), Decimal("200.00"),
    )
    assert glosa.demand_request_id == str(solicitacao.pk) and glosa.criado_por == usuario_fgd
    assert bool(glosa.arlo_import_id) == (caminho == "arlo")


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_pago_abaixo_do_autorizado_libera_a_diferenca_sem_glosa(
    caminho, autorizada, usuario_fgd, limite_individual_rn, allocation_territorial_rn,
):
    _pagar(caminho, autorizada, Decimal("800.00"), usuario_fgd)

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert (limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado) == (
        Decimal("0"), Decimal("800.00"),
    )
    assert (allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado) == (
        Decimal("0"), Decimal("800.00"),
    )
    assert not GlosaRisk.objects.exists()


def _trilha(demand):
    """O que a conclusão deixa registrado, por entidade e em ordem: etapas,
    notificações, mudanças de status e auditoria do pagamento e do saldo."""
    solicitacoes = [str(pk) for pk in demand.solicitacoes.values_list("pk", flat=True)]
    auditoria = AuditLog.objects.order_by("id")
    return {
        "etapas": list(demand.etapas.order_by("criado_em", "pk").values_list("etapa", "acao", "responsavel_id")),
        "notificacoes": list(
            Notification.objects.filter(link__endswith=f"/sgd/demandas/{demand.pk}")
            .order_by("id").values_list("evento", "user_id", "tipo")
        ),
        "status": [
            (e.valores_anteriores, e.valores_novos, e.user_id)
            for e in auditoria.filter(entidade="Demand", entidade_id=str(demand.pk))
        ],
        "solicitacao": list(
            auditoria.filter(entidade__in=["DemandRequest", "DemandIndividualLimit"], entidade_id__in=solicitacoes)
            .values_list("entidade", "acao", "user_id")
        ),
        "saldo": list(
            auditoria.filter(Q(entidade="BudgetTransaction", valores_novos__demanda=demand.pk))
            .values_list("acao", "user_id")
        ),
    }


def test_tela_e_planilha_deixam_a_mesma_trilha(
    autorizada, activity_rn, solicitante_rn, rubrica_diarias, aprovadores, usuario_fgd,
):
    pela_planilha = _outra_autorizada(activity_rn, solicitante_rn, rubrica_diarias, aprovadores)

    _pagar("tela", autorizada, Decimal("1200.00"), usuario_fgd)
    _pagar("arlo", pela_planilha, Decimal("1200.00"), usuario_fgd)

    tela, planilha = _trilha(autorizada), _trilha(pela_planilha)
    assert tela == planilha
    assert [etapa for etapa, _, _ in tela["etapas"]][-2:] == ["atendimento", "atendimento"]
    assert ("DemandRequest", "pagamento", usuario_fgd.pk) in tela["solicitacao"]
    origens = AuditLog.objects.filter(acao="pagamento").order_by("id").values_list("valores_novos__origem", flat=True)
    assert list(origens) == [workflow_service.ORIGEM_USUARIO, workflow_service.ORIGEM_ARLO]


@pytest.fixture
def com_duas_solicitacoes(demand_request_rn, solicitante_rn, aprovadores, rubrica_diarias,
                          allocation_territorial_rn, limite_individual_rn):
    DemandRequestFactory(
        demanda=demand_request_rn.demanda, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=Decimal("500"),
    )
    return _autorizar_pelo_fluxo(demand_request_rn.demanda, solicitante_rn, aprovadores)


def test_conclusao_pela_tela_depois_de_pagamento_parcial_pelo_arlo(com_duas_solicitacoes, usuario_fgd):
    paga_pelo_arlo, restante = com_duas_solicitacoes.solicitacoes.order_by("pk")
    processar_importacao(_importar([_linha(paga_pelo_arlo, valor="1000,00")], usuario_fgd))
    com_duas_solicitacoes.refresh_from_db()
    assert com_duas_solicitacoes.status == "em_atendimento"

    with pytest.raises(RegraDeNegocio):
        workflow_service.executar_transicao(
            com_duas_solicitacoes, "concluida", ator=usuario_fgd,
            valores_pagos={paga_pelo_arlo.pk: Decimal("1000"), restante.pk: Decimal("500")},
        )
    with pytest.raises(RegraDeNegocio):
        workflow_service.executar_transicao(com_duas_solicitacoes, "concluida", ator=usuario_fgd, valores_pagos={})

    workflow_service.executar_transicao(
        com_duas_solicitacoes, "concluida", ator=usuario_fgd, valores_pagos={restante.pk: Decimal("450")},
    )

    com_duas_solicitacoes.refresh_from_db()
    assert com_duas_solicitacoes.status == "concluida"
    assert dict(DemandRequest.objects.filter(demanda=com_duas_solicitacoes).values_list("pk", "valor_pago")) == {
        paga_pelo_arlo.pk: Decimal("1000.00"), restante.pk: Decimal("450.00"),
    }


def test_api_concluir_aceita_pago_acima_do_autorizado(auth_client_fgd, autorizada, usuario_fgd):
    solicitacao = autorizada.solicitacoes.get()
    workflow_service.executar_transicao(autorizada, "em_atendimento", ator=usuario_fgd)

    resposta = auth_client_fgd.post(
        f"/api/v1/sgd/demandas/{autorizada.pk}/concluir/",
        {"valores_pagos": {str(solicitacao.pk): "1200.00"}}, format="json",
    )

    assert resposta.status_code == 200, resposta.data
    assert resposta.data["status"] == "concluida"
    assert GlosaRisk.objects.get().excedente == Decimal("200.00")
