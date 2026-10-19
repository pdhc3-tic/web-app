"""Solicitação de recurso extra (SGP §6.6): pedido, parecer, decisão da UGP e remanejamento."""
import threading
import time
from decimal import Decimal

import pytest
from django.db import connection, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification
from apps.core.models.user_profile import UserProfile
from apps.sgd.models import DemandIndividualLimit, DemandRequest, DemandTypeRubricaMapping
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
from apps.sgd.services import recurso_extra as recurso_extra_service
from apps.sgd.tests.factories import (
    BudgetIncreaseRequestFactory,
    DemandFactory,
    DemandRequestFactory,
    DemandTypeRubricaMappingFactory,
)
from apps.sgp.models import BudgetAllocation, BudgetIncreaseRequest, BudgetTransfer
from apps.sgp.services import budget as budget_service
from apps.sgp.tests.factories import (
    ActivityFactory,
    BudgetAllocationFactory,
    BudgetRubricaFactory,
    WorkPlanAcaoFactory,
)

pytestmark = pytest.mark.django_db

DEMANDAS = "/api/v1/sgd/demandas/"
REMANEJAMENTOS = "/api/v1/sgd/remanejamentos/"
JUSTIFICATIVA = "Limite individual esgotado antes do fim do período."
APROVAR = {"decisao": "aprovar", "justificativa": "Procede."}


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


@pytest.fixture
def demanda(demand_request_rn, allocation_territorial_rn, limite_individual_rn):
    """Demanda em rascunho cujo pedido de R$ 1.000 só cabe depois de aumentar o limite."""
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_limite=Decimal("300"))
    return demand_request_rn.demanda


def _solicitar(user, demanda, **corpo):
    corpo = {"rubrica": "diarias", "valor_solicitado": "700", "justificativa": JUSTIFICATIVA, **corpo}
    return _cliente(user).post(f"{DEMANDAS}{demanda.pk}/solicitar-recurso-extra/", corpo, format="json")


def _acao(user, pedido_id, nome, corpo=None):
    return _cliente(user).post(f"{REMANEJAMENTOS}{pedido_id}/{nome}/", corpo or {}, format="json")


@pytest.fixture
def pedido(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda)
    assert resposta.status_code == 201, resposta.data
    return BudgetIncreaseRequest.objects.get(pk=resposta.data["id"])


@pytest.fixture
def pedido_com_parecer(pedido, usuario_articulador_rn):
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."}).status_code == 200
    pedido.refresh_from_db()
    return pedido


def _limite(solicitante, rubrica):
    return DemandIndividualLimit.objects.get(solicitante=solicitante, rubrica=rubrica).valor_limite


# ── Criação ──────────────────────────────────────────────────────────────────

def test_solicitante_cria_pedido_a_partir_da_demanda_bloqueada(demanda, solicitante_rn, rubrica_diarias):
    resposta = _solicitar(solicitante_rn, demanda)

    assert resposta.status_code == 201
    assert resposta.data["status"] == "submetida"
    assert resposta.data["rubrica"] == "diarias"
    assert resposta.data["demanda_id"] == str(demanda.pk)
    assert resposta.data["activity"] == demanda.activity_id
    assert resposta.data["user"] == solicitante_rn.pk
    assert Decimal(resposta.data["valor_solicitado"]) == Decimal("700")


def test_pedido_pode_ficar_em_rascunho(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda, submeter=False)

    assert resposta.status_code == 201
    assert resposta.data["status"] == "rascunho"


def test_pedido_exige_solicitacao_na_rubrica_da_demanda(demanda, solicitante_rn):
    from apps.sgp.tests.factories import BudgetRubricaFactory

    BudgetRubricaFactory(slug="passagens-aereas", nome="Passagens")

    assert _solicitar(solicitante_rn, demanda, rubrica="passagens-aereas").status_code == 400


@pytest.mark.parametrize("status", ["submetida", "pre_autorizada", "autorizada", "concluida", "cancelada"])
def test_so_demanda_em_rascunho_ou_devolvida_pede_recurso_extra(demanda, solicitante_rn, status):
    demanda.status = status
    demanda.save(update_fields=["status"])

    assert _solicitar(solicitante_rn, demanda).status_code == 400


def test_valor_e_justificativa_sao_obrigatorios(demanda, solicitante_rn):
    assert _solicitar(solicitante_rn, demanda, valor_solicitado="0").status_code == 400
    assert _solicitar(solicitante_rn, demanda, justificativa="  ").status_code == 400


def test_valor_omitido_assume_o_deficit_do_limite_individual(demanda, solicitante_rn):
    corpo = {"rubrica": "diarias", "justificativa": JUSTIFICATIVA}

    resposta = _cliente(solicitante_rn).post(
        f"{DEMANDAS}{demanda.pk}/solicitar-recurso-extra/", corpo, format="json",
    )

    assert resposta.status_code == 201
    assert Decimal(resposta.data["valor_solicitado"]) == Decimal("700")


def test_valor_abaixo_do_deficit_retorna_400(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda, valor_solicitado="699.99")

    assert resposta.status_code == 400
    assert "valor_solicitado" in resposta.data
    assert not BudgetIncreaseRequest.objects.exists()


def test_valor_acima_do_deficit_e_aceito_e_a_ugp_pode_conceder_menos(demanda, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda, valor_solicitado="900")

    assert resposta.status_code == 201
    assert Decimal(resposta.data["valor_solicitado"]) == Decimal("900")


def test_demanda_sem_deficit_nao_pede_recurso_extra(demanda, solicitante_rn, limite_individual_rn):
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_limite=Decimal("1000"))

    resposta = _solicitar(solicitante_rn, demanda)

    assert resposta.status_code == 400
    assert "demanda" in resposta.data
    assert not BudgetIncreaseRequest.objects.exists()


def test_so_um_pedido_em_andamento_por_demanda_e_rubrica(demanda, pedido, solicitante_rn):
    resposta = _solicitar(solicitante_rn, demanda)

    assert resposta.status_code == 400
    assert BudgetIncreaseRequest.objects.count() == 1


def test_pedido_terminal_libera_um_novo_pedido(demanda, pedido_com_parecer, solicitante_rn, usuario_ugp):
    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "Sem saldo."})

    assert _solicitar(solicitante_rn, demanda).status_code == 201


@pytest.mark.django_db(transaction=True)
def test_criacoes_simultaneas_geram_um_so_pedido(demanda, solicitante_rn, rubrica_diarias):
    barreira = threading.Barrier(2)
    resultados = []

    def tentar():
        try:
            barreira.wait()
            recurso_extra_service.criar(
                demanda=demanda, rubrica=rubrica_diarias, justificativa=JUSTIFICATIVA, usuario=solicitante_rn,
            )
            resultados.append("criado")
        except ValidationError:
            resultados.append("recusado")
        finally:
            connection.close()

    threads = [threading.Thread(target=tentar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(resultados) == ["criado", "recusado"]
    assert BudgetIncreaseRequest.objects.count() == 1


def test_edicao_do_valor_tambem_respeita_o_deficit(pedido, solicitante_rn, usuario_articulador_rn):
    _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": "Ajuste."})

    resposta = _cliente(solicitante_rn).patch(f"{REMANEJAMENTOS}{pedido.pk}/", {"valor_solicitado": "650"}, format="json")

    assert resposta.status_code == 400
    pedido.refresh_from_db()
    assert pedido.valor_solicitado == Decimal("700")
    ajustado = _cliente(solicitante_rn).patch(f"{REMANEJAMENTOS}{pedido.pk}/", {"valor_solicitado": "800"}, format="json")
    assert ajustado.status_code == 200


def test_outro_usuario_nao_pede_recurso_extra_para_a_demanda(demanda, usuario_articulador_rn, usuario_ugp):
    assert _solicitar(usuario_articulador_rn, demanda).status_code == 403
    assert _solicitar(usuario_ugp, demanda).status_code == 403


# ── Listagem e escopo ────────────────────────────────────────────────────────

@pytest.fixture
def pedido_do_ce(municipio_ce, territory_ce):
    from apps.core.tests.factories import RoleFactory, UserFactory

    role = RoleFactory(slug="adt-acr", nome="ADT / ACR")
    usuario = UserFactory(email="adt.ce@test.com", profiles=[(role, territory_ce)])
    atividade = ActivityFactory(municipio=municipio_ce, acao=WorkPlanAcaoFactory())
    return BudgetIncreaseRequestFactory(user=usuario, activity=atividade, status="com_parecer")


def _ids(resposta):
    return {item["id"] for item in resposta.data["results"]}


def test_ugp_ve_a_fila_de_pedidos_com_parecer_por_padrao(pedido, pedido_com_parecer, pedido_do_ce, usuario_ugp):
    resposta = _cliente(usuario_ugp).get(REMANEJAMENTOS)

    assert resposta.status_code == 200
    assert _ids(resposta) == {pedido_com_parecer.pk, pedido_do_ce.pk}


def test_ugp_ve_todos_os_status_com_filtro(pedido, pedido_do_ce, usuario_ugp):
    todos = _cliente(usuario_ugp).get(f"{REMANEJAMENTOS}?status=todos")
    submetidos = _cliente(usuario_ugp).get(f"{REMANEJAMENTOS}?status=submetida&status=devolvida")

    assert _ids(todos) == {pedido.pk, pedido_do_ce.pk}
    assert _ids(submetidos) == {pedido.pk}


def test_articulador_so_ve_os_pedidos_do_proprio_estado(pedido, pedido_do_ce, usuario_articulador_rn):
    resposta = _cliente(usuario_articulador_rn).get(REMANEJAMENTOS)

    assert _ids(resposta) == {pedido.pk}
    assert _cliente(usuario_articulador_rn).get(f"{REMANEJAMENTOS}{pedido_do_ce.pk}/").status_code == 404


def test_solicitante_so_ve_os_proprios_pedidos(pedido, pedido_do_ce, solicitante_rn):
    resposta = _cliente(solicitante_rn).get(REMANEJAMENTOS)

    assert _ids(resposta) == {pedido.pk}
    assert _cliente(solicitante_rn).get(f"{REMANEJAMENTOS}{pedido_do_ce.pk}/").status_code == 404


def test_fgd_le_mas_nao_decide(pedido_com_parecer, usuario_fgd):
    assert _cliente(usuario_fgd).get(f"{REMANEJAMENTOS}{pedido_com_parecer.pk}/").status_code == 200
    assert _acao(usuario_fgd, pedido_com_parecer.pk, "decidir", APROVAR).status_code == 403


def test_listagem_exige_autenticacao():
    assert APIClient().get(REMANEJAMENTOS).status_code == 401


# ── Máquina de estados ───────────────────────────────────────────────────────

def test_rascunho_so_vai_para_submetida(demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    pedido_id = _solicitar(solicitante_rn, demanda, submeter=False).data["id"]

    assert _acao(usuario_articulador_rn, pedido_id, "parecer", {"parecer": "x"}).status_code == 400
    assert _acao(usuario_ugp, pedido_id, "decidir", APROVAR).status_code == 400
    assert _acao(solicitante_rn, pedido_id, "submeter").data["status"] == "submetida"


def test_ciclo_completo_com_devolucao_e_reenvio(pedido, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    devolvido = _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": "Detalhe o valor."})
    assert devolvido.data["status"] == "devolvida"
    assert devolvido.data["parecer_articulador"] == "Detalhe o valor."

    editado = _cliente(solicitante_rn).patch(
        f"{REMANEJAMENTOS}{pedido.pk}/", {"valor_solicitado": "800", "justificativa": "Valor corrigido."}, format="json",
    )
    assert editado.status_code == 200
    assert Decimal(editado.data["valor_solicitado"]) == Decimal("800")

    assert _acao(solicitante_rn, pedido.pk, "submeter").data["status"] == "submetida"
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."}).data["status"] == "com_parecer"
    decidido = _acao(usuario_ugp, pedido.pk, "decidir", APROVAR)
    assert decidido.data["status"] == "aprovada"
    assert decidido.data["decidido_por"] == usuario_ugp.pk
    assert decidido.data["decidido_em"] is not None


def test_edicao_so_em_rascunho_ou_devolvida(pedido, solicitante_rn):
    resposta = _cliente(solicitante_rn).patch(f"{REMANEJAMENTOS}{pedido.pk}/", {"justificativa": "x"}, format="json")

    assert resposta.status_code == 400


def test_pedido_decidido_nao_muda_mais(pedido_com_parecer, usuario_ugp, usuario_articulador_rn):
    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR).status_code == 200

    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "x"}).status_code == 400
    assert _acao(usuario_articulador_rn, pedido_com_parecer.pk, "devolver", {"justificativa": "x"}).status_code == 400


def test_decisao_exige_parecer_antes(pedido, usuario_ugp):
    assert _acao(usuario_ugp, pedido.pk, "decidir", APROVAR).status_code == 400


def test_parecer_e_devolucao_exigem_texto(pedido, usuario_articulador_rn):
    assert _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "  "}).status_code == 400
    assert _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": ""}).status_code == 400


def test_so_o_articulador_do_estado_emite_parecer(pedido, solicitante_rn, usuario_ugp, usuario_articulador_ce):
    assert _acao(solicitante_rn, pedido.pk, "parecer", {"parecer": "x"}).status_code == 403
    assert _acao(usuario_ugp, pedido.pk, "parecer", {"parecer": "x"}).status_code == 403
    assert _acao(usuario_articulador_ce, pedido.pk, "parecer", {"parecer": "x"}).status_code == 404


def test_so_a_ugp_decide(pedido_com_parecer, solicitante_rn, usuario_articulador_rn):
    assert _acao(solicitante_rn, pedido_com_parecer.pk, "decidir", APROVAR).status_code == 403
    assert _acao(usuario_articulador_rn, pedido_com_parecer.pk, "decidir", APROVAR).status_code == 403


def test_so_o_solicitante_submete_e_edita(demanda, solicitante_rn, usuario_articulador_rn):
    pedido_id = _solicitar(solicitante_rn, demanda, submeter=False).data["id"]

    assert _acao(usuario_articulador_rn, pedido_id, "submeter").status_code == 403
    assert _cliente(usuario_articulador_rn).patch(
        f"{REMANEJAMENTOS}{pedido_id}/", {"justificativa": "x"}, format="json",
    ).status_code == 403


# ── Decisão: efeito no limite ────────────────────────────────────────────────

def test_aprovacao_eleva_o_limite_e_libera_a_submissao(
    demanda, pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias,
):
    with pytest.raises(ValidationError), transaction.atomic():
        demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 200
    assert Decimal(resposta.data["valor_aprovado"]) == Decimal("700")
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1000")
    demanda.refresh_from_db()
    assert demanda.status == "rascunho"  # não é submetida sozinha
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


def test_recusa_mantem_o_bloqueio_da_demanda(demanda, pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "Sem saldo."})

    assert resposta.status_code == 200
    assert resposta.data["status"] == "recusada"
    assert resposta.data["valor_aprovado"] is None
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    with pytest.raises(ValidationError), transaction.atomic():
        demand_service.submeter_demanda(demanda, usuario=solicitante_rn)


def test_recusa_sem_justificativa_retorna_400(pedido_com_parecer, usuario_ugp):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar"})

    assert resposta.status_code == 400
    assert "justificativa" in resposta.data
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"


@pytest.mark.parametrize("corpo", [{"decisao": "aprovar"}, {"decisao": "aprovar", "justificativa": "  "}])
def test_aprovacao_integral_sem_justificativa_retorna_400(
    pedido_com_parecer, usuario_ugp, solicitante_rn, rubrica_diarias, corpo,
):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", corpo)

    assert resposta.status_code == 400
    assert "justificativa" in resposta.data
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_aprovacao_parcial_eleva_o_limite_so_pelo_valor_aprovado(
    pedido_com_parecer, solicitante_rn, usuario_ugp, rubrica_diarias,
):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        "decisao": "aprovar_parcialmente", "valor_aprovado": "400", "justificativa": "Só há saldo para parte.",
    })

    assert resposta.status_code == 200
    assert resposta.data["status"] == "aprovada_parcialmente"
    assert Decimal(resposta.data["valor_aprovado"]) == Decimal("400")
    assert resposta.data["justificativa_decisao"] == "Só há saldo para parte."
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("700")


@pytest.mark.parametrize("corpo", [
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "400"},
    {"decisao": "aprovar_parcialmente", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "700", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "900", "justificativa": "x"},
    {"decisao": "aprovar_parcialmente", "valor_aprovado": "0", "justificativa": "x"},
    {"decisao": "talvez"},
])
def test_decisao_invalida_retorna_400(pedido_com_parecer, usuario_ugp, rubrica_diarias, solicitante_rn, corpo):
    assert _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", corpo).status_code == 400
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_aprovacao_cria_o_limite_quando_o_usuario_nao_tem(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias,
):
    DemandIndividualLimit.objects.filter(solicitante=solicitante_rn).delete()
    pedido = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "1000")

    assert _acao(usuario_ugp, pedido.pk, "decidir", APROVAR).status_code == 200

    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1000")


# ── Decisão: déficit revalidado ──────────────────────────────────────────────

def _pedido_com_parecer(demanda, solicitante, articulador, valor):
    resposta = _solicitar(solicitante, demanda, valor_solicitado=valor)
    assert resposta.status_code == 201, resposta.data
    assert _acao(articulador, resposta.data["id"], "parecer", {"parecer": "Procede."}).status_code == 200
    return BudgetIncreaseRequest.objects.get(pk=resposta.data["id"])


def _solicitacao_em_outra_demanda(demanda, rubrica, valor):
    """Do mesmo solicitante e da mesma Atividade: consome o mesmo limite individual e o mesmo pool."""
    outra = DemandFactory(activity=demanda.activity, solicitante=demanda.solicitante, status="rascunho")
    return DemandRequestFactory(demanda=outra, tipo="diaria", rubrica=rubrica, valor_estimado=valor)


def test_aprovacao_com_deficit_maior_que_o_solicitado_retorna_400(
    pedido_com_parecer, demand_request_rn, usuario_ugp, solicitante_rn, rubrica_diarias,
):
    DemandRequest.objects.filter(pk=demand_request_rn.pk).update(valor_estimado=Decimal("1500"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 400
    assert "valor_aprovado" in resposta.data
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_aprovacao_revalida_o_limite_consumido_por_outra_demanda(
    demanda, pedido_com_parecer, usuario_ugp, solicitante_rn, rubrica_diarias,
):
    concorrente = _solicitacao_em_outra_demanda(demanda, rubrica_diarias, Decimal("100"))
    balance_service.reservar_duas_travas(demand_request=concorrente, usuario=solicitante_rn)

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 400
    assert "valor_aprovado" in resposta.data
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_aprovacao_com_deficit_menor_que_o_solicitado_concede_o_solicitado(
    pedido_com_parecer, demand_request_rn, usuario_ugp, solicitante_rn, rubrica_diarias,
):
    DemandRequest.objects.filter(pk=demand_request_rn.pk).update(valor_estimado=Decimal("800"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 200
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1000")


def test_saldo_individual_negativo_entra_no_deficit(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias, limite_individual_rn,
):
    # Saldo de −R$ 200, como fica depois de um excedente autorizado.
    DemandIndividualLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("500"))

    assert _solicitar(solicitante_rn, demanda, valor_solicitado="1000").status_code == 400
    sem_valor = _cliente(solicitante_rn).post(
        f"{DEMANDAS}{demanda.pk}/solicitar-recurso-extra/",
        {"rubrica": "diarias", "justificativa": JUSTIFICATIVA}, format="json",
    )
    assert Decimal(sem_valor.data["valor_solicitado"]) == Decimal("1200")
    _acao(usuario_articulador_rn, sem_valor.data["id"], "parecer", {"parecer": "Procede."})

    assert _acao(usuario_ugp, sem_valor.data["id"], "decidir", APROVAR).status_code == 200

    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1500")
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


# ── Pool territorial e remanejamento ─────────────────────────────────────────

@pytest.fixture
def alocacao_estadual(allocation_territorial_rn, activity_rn, rubrica_diarias):
    return BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, nivel=BudgetAllocation.Nivel.ESTADUAL,
        estado=activity_rn.municipio.state, territorio=None, valor_alocado=Decimal("50000"),
    )


def test_pool_com_saldo_nao_gera_alerta_nem_remanejamento(pedido_com_parecer, usuario_ugp):
    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.data["alerta_pool_insuficiente"] is False
    assert resposta.data["transferencia_id"] is None
    assert not BudgetTransfer.objects.exists()


def test_pool_sem_cobrir_o_necessario_exige_origem_e_nada_e_gravado(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, solicitante_rn, rubrica_diarias,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 400
    assert "origem_allocation" in resposta.data
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    assert not BudgetTransfer.objects.exists()


def test_remanejamento_de_pool_estadual_cobre_o_que_falta(
    demanda, pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual, solicitante_rn,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        **APROVAR, "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 200, resposta.data
    assert resposta.data["alerta_pool_insuficiente"] is False
    transferencia = BudgetTransfer.objects.get(pk=resposta.data["transferencia_id"])
    assert transferencia.tipo == "entre_niveis"
    assert transferencia.valor == Decimal("800")  # 1000 que a demanda reserva − 200 que o pool já tinha
    assert (transferencia.saldo_origem_antes, transferencia.saldo_origem_depois) == (Decimal("50000"), Decimal("49200"))
    assert (transferencia.saldo_destino_antes, transferencia.saldo_destino_depois) == (Decimal("200"), Decimal("1000"))
    assert transferencia.aprovado_por == usuario_ugp
    assert transferencia.increase_request == pedido_com_parecer
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_alocado == Decimal("1000")
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


def test_pool_com_saldo_negativo_remaneja_o_deficit_inteiro(
    demanda, pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual, solicitante_rn,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(
        valor_alocado=Decimal("200"), valor_comprometido=Decimal("400"),
    )

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        **APROVAR, "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 200, resposta.data
    transferencia = BudgetTransfer.objects.get()
    assert transferencia.valor == Decimal("1200")
    assert (transferencia.saldo_destino_antes, transferencia.saldo_destino_depois) == (Decimal("-200"), Decimal("1000"))
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


def test_pedido_sem_territorio_resolvivel_nao_e_aprovado(pedido_com_parecer, usuario_ugp, solicitante_rn, rubrica_diarias):
    UserProfile.objects.filter(user=solicitante_rn).update(territorio=None)

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", APROVAR)

    assert resposta.status_code == 400
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_pedido_sem_meta_nao_e_aprovado(usuario_ugp, solicitante_rn, rubrica_diarias):
    pedido = BudgetIncreaseRequestFactory(user=solicitante_rn, rubrica=rubrica_diarias, status="com_parecer")

    resposta = _acao(usuario_ugp, pedido.pk, "decidir", APROVAR)

    assert resposta.status_code == 400
    pedido.refresh_from_db()
    assert pedido.status == "com_parecer"


def test_saldos_da_auditoria_sao_lidos_depois_do_lock(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual, monkeypatch,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    lock = BudgetAllocation.objects.select_for_update
    deslocado = []

    def travar_e_mexer_no_saldo(*args, **kwargs):
        # Um comprometimento que chega entre a consulta e o lock da origem.
        if not deslocado:
            deslocado.append(True)
            BudgetAllocation.objects.filter(pk=alocacao_estadual.pk).update(valor_comprometido=Decimal("1000"))
        return lock(*args, **kwargs)

    monkeypatch.setattr(BudgetAllocation.objects, "select_for_update", travar_e_mexer_no_saldo)

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        **APROVAR, "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 200, resposta.data
    transferencia = BudgetTransfer.objects.get()
    assert transferencia.saldo_origem_antes == Decimal("49000")
    assert transferencia.saldo_origem_depois == Decimal("48200")


def test_decisao_trava_o_limite_individual_antes_das_alocacoes(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual,
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))

    with CaptureQueriesContext(connection) as consultas:
        resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
            **APROVAR, "origem_allocation": alocacao_estadual.pk,
        })

    assert resposta.status_code == 200
    nomes = {
        "sgd_demandindividuallimit": "limite", "sgd_demandrequest": "solicitacao",
        "sgp_budgetallocation": "alocacao", "sgd_demand": "demanda",
    }
    travas = [q["sql"] for q in consultas if "FOR UPDATE" in q["sql"]]
    tabelas = [nome for sql in travas for tabela, nome in nomes.items() if f'"{tabela}"' in sql]
    # A submissão e o cancelamento só atualizam a Demand depois do limite: travá-la antes
    # dele inverteria a ordem.
    assert (
        tabelas.index("limite") < tabelas.index("demanda")
        < tabelas.index("solicitacao") < tabelas.index("alocacao")
    )


# ── Concorrência entre conexões ──────────────────────────────────────────────

def _esperar_alguem_bloqueado(timeout=10):
    """Espera outra conexão ficar parada num lock de linha. Roda na thread do teste, em
    autocommit: cada consulta abre um snapshot novo de `pg_stat_activity`."""
    prazo = time.monotonic() + timeout
    while time.monotonic() < prazo:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
            )
            if cursor.fetchone()[0]:
                return
        time.sleep(0.02)
    raise AssertionError("Nenhuma conexão ficou esperando lock.")


def _decidir_contra(pedido, *, travar, mexer, usuario, **corpo):
    """A thread B executa `travar` e segura a transação; a decisão (thread A) começa e fica
    bloqueada no que B travou; só então B executa `mexer` e commita. Devolve o resultado
    da decisão e as exceções de cada thread."""
    b_travou, b_pode_seguir = threading.Event(), threading.Event()
    resultado, erros = {}, {}

    def concorrente():
        try:
            with transaction.atomic():
                travar()
                b_travou.set()
                b_pode_seguir.wait(timeout=10)
                mexer()
        except Exception as exc:
            erros["concorrente"] = exc
        finally:
            b_travou.set()
            connection.close()

    def decisao():
        try:
            resultado["decisao"] = recurso_extra_service.decidir(pedido, usuario=usuario, **corpo)
        except Exception as exc:
            erros["decisao"] = exc
        finally:
            connection.close()

    thread_b = threading.Thread(target=concorrente)
    thread_b.start()
    assert b_travou.wait(timeout=10)
    thread_a = threading.Thread(target=decisao)
    thread_a.start()
    try:
        _esperar_alguem_bloqueado()
    finally:
        b_pode_seguir.set()
        thread_b.join(timeout=15)
        thread_a.join(timeout=15)
    assert not thread_a.is_alive() and not thread_b.is_alive()
    return resultado.get("decisao"), erros


@pytest.mark.django_db(transaction=True)
def test_reserva_concorrente_do_solicitante_e_vista_pela_decisao_sem_deadlock(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias,
    allocation_territorial_rn, alocacao_estadual,
):
    """A reserva trava limite → alocação; a decisão, também. Ela espera o limite sem
    segurar alocação (senão a reserva entraria em deadlock) e lê limite e pool já com
    a reserva concorrente."""
    pedido = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "900")
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    concorrente = _solicitacao_em_outra_demanda(demanda, rubrica_diarias, Decimal("100"))

    resultado, erros = _decidir_contra(
        pedido,
        travar=lambda: DemandIndividualLimit.objects.select_for_update().get(
            solicitante=solicitante_rn, rubrica=rubrica_diarias,
        ),
        mexer=lambda: balance_service.reservar_duas_travas(demand_request=concorrente, usuario=solicitante_rn),
        usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.", origem_allocation=alocacao_estadual,
    )

    assert erros == {}
    transferencia = resultado["transferencia"]
    # Pool: 200 − 100 reservados pela concorrente = 100; a demanda precisa de 1.000.
    assert transferencia.valor == Decimal("900")
    assert (transferencia.saldo_destino_antes, transferencia.saldo_destino_depois) == (Decimal("100"), Decimal("1000"))
    limite = DemandIndividualLimit.objects.get(solicitante=solicitante_rn, rubrica=rubrica_diarias)
    assert (limite.valor_limite, limite.valor_comprometido) == (Decimal("1200"), Decimal("100"))
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    assert demanda.status == "submetida"


@pytest.mark.django_db(transaction=True)
def test_pool_suficiente_na_consulta_e_consumido_antes_do_lock_exige_origem(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias, allocation_territorial_rn,
):
    """Outra reserva (de outro solicitante, sem disputar o limite) segura a alocação
    territorial: a decisão consulta o pool ainda suficiente, espera o lock e precisa
    reler o saldo, que a reserva deixou abaixo do necessário."""
    pedido = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "700")
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("1050"))

    def reservar_no_pool():
        budget_service.reservar(
            allocation=allocation_territorial_rn, valor=Decimal("100"), demanda_id="concorrente",
            usuario=usuario_ugp, justificativa="Reserva concorrente.",
        )

    resultado, erros = _decidir_contra(
        pedido,
        travar=lambda: BudgetAllocation.objects.select_for_update().get(pk=allocation_territorial_rn.pk),
        mexer=reservar_no_pool,
        usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.",
    )

    assert resultado is None
    assert set(erros) == {"decisao"}
    assert isinstance(erros["decisao"], ValidationError)
    assert "origem_allocation" in erros["decisao"].detail
    pedido.refresh_from_db()
    assert pedido.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("100")


CAMPOS_GRAFICO = {
    "tipo_material": "banner", "quantidade": 1,
    "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
}


@pytest.fixture
def grafico_em_diarias(rubrica_diarias):
    DemandTypeRubricaMapping.objects.filter(tipo="grafico").delete()
    return DemandTypeRubricaMappingFactory(tipo="grafico", rubrica=rubrica_diarias)


def _conferir_barrada_pelo_deficit(resultado, erros, pedido, solicitante, rubrica):
    assert resultado is None
    assert set(erros) == {"decisao"}
    assert isinstance(erros["decisao"], ValidationError)
    assert "valor_aprovado" in erros["decisao"].detail
    pedido.refresh_from_db()
    assert pedido.status == "com_parecer"
    assert _limite(solicitante, rubrica) == Decimal("300")


@pytest.mark.django_db(transaction=True)
def test_solicitacao_incluida_durante_a_decisao_entra_no_deficit(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias, grafico_em_diarias,
):
    """A inclusão trava a Demand e segura a transação: a decisão espera por ela e recalcula
    o déficit com a solicitação nova (1.000 + 500 − 300 = 1.200, acima dos 700 pedidos)."""
    pedido = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "700")

    resultado, erros = _decidir_contra(
        pedido,
        travar=lambda: demand_service.adicionar_solicitacao(
            demanda, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=Decimal("500"),
        ),
        mexer=lambda: None,
        usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.",
    )

    _conferir_barrada_pelo_deficit(resultado, erros, pedido, solicitante_rn, rubrica_diarias)
    assert DemandRequest.objects.filter(demanda=demanda, rubrica=rubrica_diarias).count() == 2


@pytest.mark.django_db(transaction=True)
def test_solicitacao_movida_para_a_rubrica_durante_a_decisao_entra_no_deficit(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias, grafico_em_diarias,
):
    """Trocar o tipo de uma solicitação de outra rubrica a traz para esta sem incluir linha
    nova: a decisão a alcança porque trava todas as solicitações da demanda."""
    pedido = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "700")
    movida = DemandRequestFactory(
        demanda=demanda, tipo="passagem", rubrica=BudgetRubricaFactory(slug="rubrica-de-origem"),
        valor_estimado=Decimal("500"),
    )

    resultado, erros = _decidir_contra(
        pedido,
        travar=lambda: demand_service.atualizar_solicitacao(
            movida, usuario=solicitante_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO,
            valor_estimado=Decimal("500"),
        ),
        mexer=lambda: None,
        usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.",
    )

    _conferir_barrada_pelo_deficit(resultado, erros, pedido, solicitante_rn, rubrica_diarias)
    movida.refresh_from_db()
    assert movida.rubrica_id == rubrica_diarias.pk


@pytest.mark.django_db(transaction=True)
def test_decisoes_simultaneas_sem_limite_criam_um_so_limite(
    demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp, rubrica_diarias,
):
    """Sem limite, o FOR UPDATE não trava nada e as duas decisões tentam criá-lo. A segunda
    espera a primeira no índice único, relê o limite que ela criou e soma o seu aumento."""
    DemandIndividualLimit.objects.filter(solicitante=solicitante_rn).delete()
    primeiro = _pedido_com_parecer(demanda, solicitante_rn, usuario_articulador_rn, "1000")
    outra = _solicitacao_em_outra_demanda(demanda, rubrica_diarias, Decimal("400")).demanda
    segundo = _pedido_com_parecer(outra, solicitante_rn, usuario_articulador_rn, "400")

    resultado, erros = _decidir_contra(
        segundo,
        travar=lambda: recurso_extra_service.decidir(
            primeiro, usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.",
        ),
        mexer=lambda: None,
        usuario=usuario_ugp, decisao="aprovar", justificativa="Procede.",
    )

    assert erros == {}
    assert resultado["pedido"].status == "aprovada"
    primeiro.refresh_from_db()
    assert primeiro.status == "aprovada"
    assert DemandIndividualLimit.objects.filter(solicitante=solicitante_rn, rubrica=rubrica_diarias).count() == 1
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("1400")


def test_remanejamento_so_pode_vir_de_saldo_estadual_ou_nacional(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, solicitante_rn, rubrica_diarias,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    outra_territorial = BudgetAllocationFactory(
        meta=allocation_territorial_rn.meta, rubrica=rubrica_diarias, valor_alocado=Decimal("9000"),
    )

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        **APROVAR, "origem_allocation": outra_territorial.pk,
    })

    assert resposta.status_code == 400
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")


def test_remanejamento_sem_saldo_na_origem_desfaz_a_decisao(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual, solicitante_rn, rubrica_diarias,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    BudgetAllocation.objects.filter(pk=alocacao_estadual.pk).update(valor_alocado=Decimal("100"))

    resposta = _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {
        **APROVAR, "origem_allocation": alocacao_estadual.pk,
    })

    assert resposta.status_code == 400
    pedido_com_parecer.refresh_from_db()
    assert pedido_com_parecer.status == "com_parecer"
    assert _limite(solicitante_rn, rubrica_diarias) == Decimal("300")
    assert not BudgetTransfer.objects.exists()


def test_remanejamento_registrado_e_imutavel(
    pedido_com_parecer, usuario_ugp, allocation_territorial_rn, alocacao_estadual,
):
    BudgetAllocation.objects.filter(pk=allocation_territorial_rn.pk).update(valor_alocado=Decimal("200"))
    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {**APROVAR, "origem_allocation": alocacao_estadual.pk})
    transferencia = BudgetTransfer.objects.get()

    transferencia.motivo = "adulterado"
    with pytest.raises(ValueError):
        transferencia.save()
    from django.db.models import ProtectedError
    with pytest.raises(ProtectedError):
        transferencia.delete()


# ── Auditoria e notificações ─────────────────────────────────────────────────

def test_toda_decisao_gera_auditoria(pedido_com_parecer, usuario_ugp, solicitante_rn):
    resposta = _cliente(usuario_ugp).post(
        f"{REMANEJAMENTOS}{pedido_com_parecer.pk}/decidir/", APROVAR, format="json",
        REMOTE_ADDR="198.51.100.9",
    )

    assert resposta.status_code == 200
    decisao = AuditLog.objects.get(entidade="BudgetIncreaseRequest", acao="recurso_extra.decidido_aprovar")
    assert decisao.user == usuario_ugp
    assert decisao.ip == "198.51.100.9"
    assert decisao.valores_anteriores == {"status": "com_parecer"}
    assert decisao.valores_novos["status"] == "aprovada"
    aumento = AuditLog.objects.get(entidade="DemandIndividualLimit", acao="aumento_limite")
    assert aumento.valores_anteriores == {"valor_limite": "300.00"}
    assert aumento.valores_novos["valor_limite"] == "1000.00"
    assert aumento.valores_novos["pedido"] == pedido_com_parecer.pk


def test_recusa_tambem_gera_auditoria(pedido_com_parecer, usuario_ugp):
    _acao(usuario_ugp, pedido_com_parecer.pk, "decidir", {"decisao": "recusar", "justificativa": "Sem saldo."})

    entrada = AuditLog.objects.get(entidade="BudgetIncreaseRequest", acao="recurso_extra.decidido_recusar")
    assert entrada.valores_novos["status"] == "recusada"
    assert not AuditLog.objects.filter(acao="aumento_limite").exists()


def test_cada_transicao_do_pedido_e_auditada(pedido, usuario_articulador_rn):
    _acao(usuario_articulador_rn, pedido.pk, "parecer", {"parecer": "Procede."})

    acoes = list(
        AuditLog.objects.filter(entidade="BudgetIncreaseRequest", entidade_id=str(pedido.pk))
        .order_by("id").values_list("acao", flat=True)
    )
    assert acoes == ["recurso_extra.criado", "recurso_extra.submetido", "recurso_extra.parecer_emitido"]


def test_notificacoes_a_cada_etapa(demanda, solicitante_rn, usuario_articulador_rn, usuario_ugp):
    pedido_id = _solicitar(solicitante_rn, demanda).data["id"]
    assert Notification.objects.filter(user=usuario_articulador_rn, evento="recurso_extra_submetido").exists()

    _acao(usuario_articulador_rn, pedido_id, "parecer", {"parecer": "Procede."})
    assert Notification.objects.filter(user=usuario_ugp, evento="recurso_extra_com_parecer").exists()

    _acao(usuario_ugp, pedido_id, "decidir", APROVAR)
    assert Notification.objects.filter(user=solicitante_rn, evento="recurso_extra_decidido").exists()


def test_devolucao_notifica_o_solicitante(pedido, solicitante_rn, usuario_articulador_rn):
    _acao(usuario_articulador_rn, pedido.pk, "devolver", {"justificativa": "Detalhe o valor."})

    assert Notification.objects.filter(user=solicitante_rn, evento="recurso_extra_devolvido").exists()
