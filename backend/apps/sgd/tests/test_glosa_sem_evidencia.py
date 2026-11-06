"""Risco de glosa da demanda executada em atividade sem evidência, nas duas ordens de evento."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.sgd.services import workflow as workflow_service
from apps.sgd.tasks import registrar_riscos_da_atividade_sem_evidencia
from apps.sgd.tests.factories import DemandFactory

# Fixtures e helpers compartilhados com a suíte de pagamento.
from apps.sgd.tests.test_arlo_integration import storage_local  # noqa: F401
from apps.sgd.tests.test_registro_pagamento import CAMINHOS, _pagar, aprovadores, autorizada  # noqa: F401
from apps.sgp.models import GlosaRisk
from apps.sgp.models.activity import Activity

pytestmark = pytest.mark.django_db

SEM_EVIDENCIA = "concluido_sem_evidencia"
TAREFA = "apps.sgd.tasks.registrar_riscos_da_atividade_sem_evidencia.delay"
RISCOS = GlosaRisk.objects.filter(tipo_situacao=GlosaRisk.Tipo.DEMANDA_SEM_EVIDENCIA)


def _deixar_sem_evidencia(demand):
    """Direto no banco: aqui importa o estado da atividade, não as regras de quem a muda."""
    Activity.objects.filter(pk=demand.activity_id).update(status=SEM_EVIDENCIA)
    demand.activity.refresh_from_db()


class TestDemandaConcluiEmAtividadeSemEvidencia:
    @pytest.mark.parametrize("caminho", CAMINHOS)
    def test_registra_com_severidade_alta_e_o_valor_pago(self, caminho, autorizada, usuario_fgd):  # noqa: F811
        _deixar_sem_evidencia(autorizada)

        _pagar(caminho, autorizada, Decimal("800.00"), usuario_fgd)

        risco = RISCOS.get()
        assert (risco.severidade, risco.valor_exposto) == (GlosaRisk.Severidade.ALTA, Decimal("800.00"))
        assert (risco.entidade, risco.entidade_id) == (GlosaRisk.ENTIDADE_DEMANDA, str(autorizada.pk))
        assert (risco.activity_id, risco.demanda_id) == (autorizada.activity_id, str(autorizada.pk))
        assert risco.demand_request_id == ""
        assert (risco.valor_autorizado, risco.valor_pago) == (None, None)

    def test_convive_com_o_risco_de_pago_acima_do_autorizado(self, autorizada, usuario_fgd):  # noqa: F811
        _deixar_sem_evidencia(autorizada)

        _pagar("tela", autorizada, Decimal("1200.00"), usuario_fgd)

        assert set(GlosaRisk.objects.values_list("tipo_situacao", "valor_exposto")) == {
            (GlosaRisk.Tipo.PAGO_ACIMA_AUTORIZADO, Decimal("200.00")),
            (GlosaRisk.Tipo.DEMANDA_SEM_EVIDENCIA, Decimal("1200.00")),
        }

    def test_atividade_ainda_em_andamento_nao_registra(self, autorizada, usuario_fgd):  # noqa: F811
        Activity.objects.filter(pk=autorizada.activity_id).update(status="em_andamento")
        autorizada.activity.refresh_from_db()

        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)

        assert not RISCOS.exists()


class TestAtividadePassaASemEvidencia:
    def _mudar_status(self, demand, status="em_andamento"):
        atividade = Activity.objects.get(pk=demand.activity_id)
        atividade.status = status
        atividade.save(update_fields=["status"])

    def test_agenda_a_tarefa_depois_do_commit(self, django_capture_on_commit_callbacks, autorizada):  # noqa: F811
        with patch(TAREFA) as delay:
            with django_capture_on_commit_callbacks(execute=True):
                self._mudar_status(autorizada, SEM_EVIDENCIA)

        delay.assert_called_once_with(autorizada.activity_id)

    def test_salvar_de_novo_nao_agenda(self, django_capture_on_commit_callbacks, autorizada):  # noqa: F811
        Activity.objects.filter(pk=autorizada.activity_id).update(status=SEM_EVIDENCIA)

        with patch(TAREFA) as delay:
            with django_capture_on_commit_callbacks(execute=True):
                self._mudar_status(autorizada, SEM_EVIDENCIA)

        delay.assert_not_called()

    def test_outro_status_nao_agenda(self, django_capture_on_commit_callbacks, autorizada):  # noqa: F811
        with patch(TAREFA) as delay:
            with django_capture_on_commit_callbacks(execute=True):
                self._mudar_status(autorizada, "em_andamento")

        delay.assert_not_called()

    def test_broker_fora_nao_derruba_quem_salvou(self, django_capture_on_commit_callbacks, autorizada):  # noqa: F811
        with patch(TAREFA, side_effect=OSError("broker fora")):
            with django_capture_on_commit_callbacks(execute=True):
                self._mudar_status(autorizada, SEM_EVIDENCIA)

        assert Activity.objects.get(pk=autorizada.activity_id).status == SEM_EVIDENCIA

    def test_tarefa_registra_as_concluidas_e_nao_duplica(self, autorizada, usuario_fgd):  # noqa: F811
        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)
        aberta = DemandFactory(activity=autorizada.activity, status="submetida")
        _deixar_sem_evidencia(autorizada)

        assert registrar_riscos_da_atividade_sem_evidencia(autorizada.activity_id) == 1
        assert registrar_riscos_da_atividade_sem_evidencia(autorizada.activity_id) == 1

        risco = RISCOS.get()
        assert risco.demanda_id == str(autorizada.pk)
        assert risco.valor_exposto == Decimal("800.00")
        assert not RISCOS.filter(demanda_id=str(aberta.pk)).exists()

    def test_tarefa_sem_demanda_concluida_nao_registra(self, autorizada):  # noqa: F811
        assert registrar_riscos_da_atividade_sem_evidencia(autorizada.activity_id) == 0
        assert not RISCOS.exists()


def test_registrar_de_novo_mantem_o_primeiro_registro(autorizada, usuario_fgd):  # noqa: F811
    _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)
    autorizada.refresh_from_db()

    workflow_service.registrar_demanda_sem_evidencia(autorizada, usuario=usuario_fgd)
    autorizada.valor_pago_total = Decimal("1.00")
    workflow_service.registrar_demanda_sem_evidencia(autorizada)

    risco = RISCOS.get()
    assert (risco.valor_exposto, risco.criado_por) == (Decimal("800.00"), usuario_fgd)
