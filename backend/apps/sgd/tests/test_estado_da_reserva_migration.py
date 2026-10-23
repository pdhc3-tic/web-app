"""Migration que preenche o estado da reserva a partir do AuditLog."""
import importlib
from decimal import Decimal

import pytest
from django.apps import apps

from apps.core.models.audit_log import AuditLog
from apps.sgd.models import DemandIndividualLimit, DemandRequest
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.sgd.migrations.0013_preencher_estado_da_reserva")


def _evento(solicitacao_ou_id, acao, **novos):
    entidade_id = getattr(solicitacao_ou_id, "pk", solicitacao_ou_id)
    AuditLog.objects.create(
        acao=acao, modulo="sgd", entidade="DemandIndividualLimit", entidade_id=str(entidade_id),
        valores_novos={chave: str(valor) for chave, valor in novos.items()},
    )


def _estado(solicitacao):
    solicitacao.refresh_from_db()
    return solicitacao.valor_reservado, solicitacao.valor_executado


def _preencher():
    migration.preencher(apps, None)


@pytest.fixture
def solicitacoes(activity_rn, solicitante_rn, rubrica_diarias):
    def criar(valor="1000"):
        return DemandRequestFactory(
            demanda=DemandFactory(activity=activity_rn, solicitante=solicitante_rn),
            rubrica=rubrica_diarias, valor_estimado=Decimal(valor),
        )
    return criar


def _limite(solicitante, rubrica, comprometido):
    return DemandIndividualLimit.objects.create(
        solicitante=solicitante, rubrica=rubrica, valor_limite=Decimal("10000"),
        valor_comprometido=Decimal(comprometido),
    )


def test_reproduz_reserva_ajuste_liberacao_e_execucao(solicitacoes, solicitante_rn, rubrica_diarias):
    ajustada, liberada, executada, reservada_de_novo, sem_evento = (solicitacoes() for _ in range(5))
    _evento(ajustada, "reserva", valor="1000")
    _evento(ajustada, "ajuste", valor="800")
    _evento(liberada, "reserva", valor="1000")
    _evento(liberada, "liberacao", valor="1000")
    _evento(executada, "reserva", valor="1000")
    _evento(executada, "execucao", valor_pago="900")
    _evento(reservada_de_novo, "reserva", valor="1000")
    _evento(reservada_de_novo, "liberacao", valor="1000")
    _evento(reservada_de_novo, "reserva", valor="600")
    _limite(solicitante_rn, rubrica_diarias, comprometido="1400")

    _preencher()

    assert _estado(ajustada) == (Decimal("800"), None)
    assert _estado(liberada) == (Decimal("0"), None)
    assert _estado(executada) == (Decimal("1000"), Decimal("900"))
    assert _estado(reservada_de_novo) == (Decimal("600"), None)
    assert _estado(sem_evento) == (Decimal("0"), None)


def test_rodar_de_novo_da_o_mesmo_resultado(solicitacoes, solicitante_rn, rubrica_diarias):
    solicitacao = solicitacoes()
    _evento(solicitacao, "reserva", valor="1000")
    _limite(solicitante_rn, rubrica_diarias, comprometido="1000")

    _preencher()
    DemandRequest.objects.filter(pk=solicitacao.pk).update(valor_reservado=Decimal("1"))
    _preencher()

    assert _estado(solicitacao) == (Decimal("1000"), None)


def test_ignora_eventos_do_limite_que_nao_movem_reserva(solicitacoes, solicitante_rn, rubrica_diarias):
    """`aumento_limite` grava o pk do limite em `entidade_id`, que pode coincidir
    com o pk de uma solicitação."""
    solicitacao = solicitacoes()
    limite = _limite(solicitante_rn, rubrica_diarias, comprometido="0")
    _evento(solicitacao.pk, "aumento_limite", valor_limite="5000")
    _evento(limite.pk, "aumento_limite", valor_limite="5000")
    _evento(solicitacao, "remanejamento_emergencial", valor_excedente="500")

    _preencher()

    assert _estado(solicitacao) == (Decimal("0"), None)


def test_eventos_de_solicitacao_removida_nao_quebram(solicitacoes, solicitante_rn, rubrica_diarias):
    _evento(999_999, "reserva", valor="1000")
    _evento(999_999, "liberacao", valor="1000")
    _limite(solicitante_rn, rubrica_diarias, comprometido="0")

    _preencher()


def test_aborta_se_o_comprometido_do_limite_nao_fecha(solicitacoes, solicitante_rn, rubrica_diarias):
    solicitacao = solicitacoes()
    _evento(solicitacao, "reserva", valor="1000")
    limite = _limite(solicitante_rn, rubrica_diarias, comprometido="1500")

    with pytest.raises(RuntimeError, match=f"Limite #{limite.pk}: valor_comprometido=1500.00, reservas ativas somam 1000"):
        _preencher()


def test_aborta_com_reserva_ativa_sem_limite(solicitacoes, solicitante_rn, rubrica_diarias):
    solicitacao = solicitacoes()
    _evento(solicitacao, "reserva", valor="1000")

    with pytest.raises(RuntimeError, match=f"Solicitante #{solicitante_rn.pk}, rubrica #{rubrica_diarias.pk}"):
        _preencher()


def test_evento_sem_valor_aborta_apontando_o_evento(solicitacoes):
    solicitacao = solicitacoes()
    AuditLog.objects.create(
        acao="reserva", modulo="sgd", entidade="DemandIndividualLimit", entidade_id=str(solicitacao.pk),
        valores_novos={},
    )

    with pytest.raises(RuntimeError, match=r"\(reserva\) do AuditLog sem `valor`"):
        _preencher()
