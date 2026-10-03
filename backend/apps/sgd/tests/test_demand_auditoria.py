"""Auditoria da demanda: status, saldo, IP atrás do proxy e rota de consulta."""
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.sgd.models import Demand
from apps.sgd.services import approval as approval_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import demand as demand_service
from apps.sgp.models import BudgetTransaction

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/demandas/"
IP_CLIENTE = "203.0.113.9"
IP_FORJADO = "6.6.6.6"


@pytest.fixture
def demanda(demand_request_rn, allocation_territorial_rn, limite_individual_rn):
    return Demand.objects.get(pk=demand_request_rn.demanda_id)


def _cliente(user):
    cliente = APIClient()
    cliente.force_authenticate(user=user)
    return cliente


def _status(demanda):
    return list(AuditLog.objects.filter(entidade="Demand", entidade_id=str(demanda.pk)).order_by("id"))


def _saldo(acao):
    return list(AuditLog.objects.filter(acao=f"saldo.{acao}").order_by("id"))


def _decimais(saldo):
    return {campo: Decimal(valor) for campo, valor in saldo.items()}


def test_cada_transicao_gera_exatamente_uma_entrada_com_usuario(
    demanda, demand_request_rn, solicitante_rn, usuario_articulador_rn, usuario_ugp, usuario_fgd,
):
    passos = [
        (lambda: demand_service.submeter_demanda(demanda, usuario=solicitante_rn), solicitante_rn, "rascunho", "submetida"),
        (lambda: approval_service.pre_autorizar(demanda, responsavel=usuario_articulador_rn), usuario_articulador_rn, "submetida", "pre_autorizada"),
        (lambda: approval_service.autorizar(demanda, responsavel=usuario_ugp), usuario_ugp, "pre_autorizada", "autorizada"),
        (lambda: approval_service.atender(demanda, responsavel=usuario_fgd), usuario_fgd, "autorizada", "em_atendimento"),
        (
            lambda: approval_service.concluir(
                demanda, responsavel=usuario_fgd, valores_pagos={demand_request_rn.pk: Decimal("900")},
            ),
            usuario_fgd, "em_atendimento", "concluida",
        ),
    ]
    for indice, (acao, usuario, de, para) in enumerate(passos, start=1):
        acao()
        entradas = [e for e in _status(demanda) if e.acao == "demanda.status_alterado"]
        assert len(entradas) == indice
        assert entradas[-1].user == usuario
        assert entradas[-1].valores_anteriores == {"status": de}
        assert entradas[-1].valores_novos == {"status": para}
        assert entradas[-1].timestamp is not None


def test_cancelamento_pelo_solicitante_gera_entrada(demanda, demand_request_rn, solicitante_rn):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    demand_service.cancelar_demanda(demanda, usuario=solicitante_rn, motivo="Mudou o plano")

    ultima = _status(demanda)[-1]
    assert (ultima.valores_anteriores, ultima.valores_novos) == ({"status": "submetida"}, {"status": "cancelada"})
    assert ultima.user == solicitante_rn


def test_cancelamento_automatico_registra_o_sistema(demanda, demand_request_rn, solicitante_rn):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    approval_service.marcar_cancelada(demanda)

    ultima = _status(demanda)[-1]
    assert ultima.acao == "demanda.status_alterado"
    assert ultima.user is None
    assert ultima.ip is None


def test_criacao_da_demanda_abre_a_trilha(activity_rn, solicitante_rn):
    demanda = demand_service.criar_demanda(
        titulo="Pedido", activity=activity_rn, justificativa="", solicitante=solicitante_rn,
    )

    (entrada,) = _status(demanda)
    assert entrada.acao == "demanda.criada"
    assert entrada.valores_anteriores == {}
    assert entrada.valores_novos == {"status": "rascunho"}
    assert entrada.user == solicitante_rn


def test_reserva_ajuste_execucao_e_liberacao_ligadas_a_transacao(
    demanda, demand_request_rn, solicitante_rn, usuario_articulador_rn, usuario_ugp, usuario_fgd,
):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    approval_service.pre_autorizar(demanda, responsavel=usuario_articulador_rn)
    approval_service.autorizar(demanda, responsavel=usuario_ugp, ajustes={demand_request_rn.pk: Decimal("1200")})
    approval_service.atender(demanda, responsavel=usuario_fgd)
    approval_service.concluir(demanda, responsavel=usuario_fgd, valores_pagos={demand_request_rn.pk: Decimal("1100")})

    por_tipo = {t.tipo: t for t in BudgetTransaction.objects.filter(demanda_id=str(demand_request_rn.pk))}
    assert set(por_tipo) == {"reserva", "ajuste", "execucao", "liberacao"}

    esperados = {
        # tipo: (comprometido antes, depois), (executado antes, depois)
        "reserva": ((0, 1000), (0, 0)),
        "ajuste": ((1000, 1200), (0, 0)),
        "execucao": ((1200, 0), (0, 1100)),
        # a diferença paga a menos só é registrada: o comprometido já saiu na execução
        "liberacao": ((0, 0), (1100, 1100)),
    }
    for tipo, ((comp_antes, comp_depois), (exec_antes, exec_depois)) in esperados.items():
        (entrada,) = _saldo(tipo)
        assert entrada.entidade == "BudgetTransaction"
        assert entrada.entidade_id == str(por_tipo[tipo].pk)
        assert entrada.valores_novos["demanda"] == demanda.pk
        assert entrada.valores_novos["solicitacao"] == demand_request_rn.pk
        anterior = _decimais(entrada.valores_anteriores["saldo"])
        posterior = _decimais(entrada.valores_novos["saldo"])
        assert (anterior["comprometido"], posterior["comprometido"]) == (comp_antes, comp_depois), tipo
        assert (anterior["executado"], posterior["executado"]) == (exec_antes, exec_depois), tipo
    assert _saldo("liberacao")[0].valores_novos["valor"] in {"100", "100.00"}


def test_liberacao_por_cancelamento_devolve_o_comprometido(demanda, demand_request_rn, solicitante_rn):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    demand_service.cancelar_demanda(demanda, usuario=solicitante_rn)

    (entrada,) = _saldo("liberacao")
    assert _decimais(entrada.valores_anteriores["saldo"])["comprometido"] == Decimal("1000")
    assert _decimais(entrada.valores_novos["saldo"])["comprometido"] == Decimal("0")
    assert entrada.user == solicitante_rn


def test_reserva_repetida_nao_duplica_a_auditoria(demanda, demand_request_rn, solicitante_rn):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    assert len(_saldo("reserva")) == 1


def test_entrada_de_auditoria_nao_pode_ser_alterada_nem_apagada(demanda, demand_request_rn, solicitante_rn):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    entrada = _status(demanda)[0]

    entrada.acao = "adulterada"
    with pytest.raises(ValueError):
        entrada.save()
    with pytest.raises(ValueError):
        entrada.delete()
    with pytest.raises((DatabaseError, ValueError)), transaction.atomic():
        AuditLog.objects.filter(pk=entrada.pk).update(acao="adulterada")
    with pytest.raises((DatabaseError, ValueError)), transaction.atomic():
        AuditLog.objects.filter(pk=entrada.pk).delete()


def test_super_admin_nao_altera_nem_apaga_auditoria_pela_api(demanda, usuario_super_admin):
    demand_service.criar_demanda(
        titulo="x", activity=demanda.activity, justificativa="", solicitante=demanda.solicitante,
    )
    entrada = AuditLog.objects.filter(entidade="Demand").first()
    cliente = _cliente(usuario_super_admin)

    assert cliente.patch(f"/api/v1/audit-logs/{entrada.pk}/", {"acao": "x"}, format="json").status_code in (404, 405)
    assert cliente.delete(f"/api/v1/audit-logs/{entrada.pk}/").status_code in (404, 405)


def test_ip_do_cliente_atras_do_proxy_ignora_o_cabecalho_forjado(demanda, demand_request_rn, solicitante_rn):
    resposta = _cliente(solicitante_rn).post(
        f"{URL}{demanda.pk}/submeter/", {}, format="json",
        REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR=f"{IP_FORJADO}, {IP_CLIENTE}",
        HTTP_USER_AGENT="pytest-agent",
    )

    assert resposta.status_code == 200, resposta.data
    entrada = [e for e in _status(demanda) if e.acao == "demanda.status_alterado"][0]
    assert entrada.ip == IP_CLIENTE
    assert entrada.user_agent == "pytest-agent"
    assert all(e.ip == IP_CLIENTE for e in _saldo("reserva"))


def test_sem_cabecalho_de_proxy_o_ip_e_o_da_conexao(demanda, demand_request_rn, solicitante_rn):
    _cliente(solicitante_rn).post(f"{URL}{demanda.pk}/submeter/", {}, format="json", REMOTE_ADDR="198.51.100.7")

    assert _status(demanda)[0].ip == "198.51.100.7"


def test_rota_devolve_a_trilha_em_ordem_cronologica(
    demanda, demand_request_rn, solicitante_rn, usuario_articulador_rn, usuario_super_admin,
):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    approval_service.pre_autorizar(demanda, responsavel=usuario_articulador_rn)

    resposta = _cliente(usuario_super_admin).get(f"{URL}{demanda.pk}/auditoria/")

    assert resposta.status_code == 200
    itens = resposta.data["results"]
    # A reserva de saldo acontece dentro da submissão, antes de o status mudar.
    assert [i["acao"] for i in itens] == [
        "saldo.reserva", "demanda.status_alterado", "demanda.status_alterado",
    ]
    assert [i["tipo"] for i in itens] == ["saldo", "status", "status"]
    assert [i["timestamp"] for i in itens] == sorted(i["timestamp"] for i in itens)
    assert itens[0]["usuario"] == {"id": solicitante_rn.pk, "nome": solicitante_rn.nome}
    assert set(itens[0]) == {"id", "tipo", "acao", "usuario", "ip", "timestamp", "valores_anteriores", "valores_novos"}


def test_rota_so_traz_a_trilha_da_propria_demanda(
    demanda, demand_request_rn, solicitante_rn, usuario_super_admin, activity_rn,
):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)
    outra = demand_service.criar_demanda(
        titulo="Outra", activity=activity_rn, justificativa="", solicitante=solicitante_rn,
    )

    resposta = _cliente(usuario_super_admin).get(f"{URL}{outra.pk}/auditoria/")

    assert [i["acao"] for i in resposta.data["results"]] == ["demanda.criada"]


def test_rota_e_paginada(demanda, demand_request_rn, solicitante_rn, usuario_super_admin):
    demand_service.submeter_demanda(demanda, usuario=solicitante_rn)

    resposta = _cliente(usuario_super_admin).get(f"{URL}{demanda.pk}/auditoria/?limit=1")

    assert resposta.data["count"] == 2
    assert len(resposta.data["results"]) == 1
    assert resposta.data["next"] is not None


def test_rota_exige_autenticacao(demanda):
    assert APIClient().get(f"{URL}{demanda.pk}/auditoria/").status_code == 401


@pytest.mark.parametrize("perfil", ["solicitante_rn", "usuario_articulador_rn", "usuario_ugp", "usuario_fgd"])
def test_rota_e_so_do_super_admin(demanda, perfil, request):
    usuario = request.getfixturevalue(perfil)

    assert _cliente(usuario).get(f"{URL}{demanda.pk}/auditoria/").status_code == 403


def test_rota_de_demanda_inexistente_retorna_404(usuario_super_admin):
    assert _cliente(usuario_super_admin).get(f"{URL}999999/auditoria/").status_code == 404
