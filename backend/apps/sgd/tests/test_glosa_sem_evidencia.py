"""Risco de glosa da demanda executada em atividade sem evidência, nas duas ordens de evento."""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from django.db import connection

from apps.core.tests.factories import UserFactory
from apps.sgd.models import Demand
from apps.sgd.services import workflow as workflow_service
from apps.sgd.tests.factories import DemandFactory

# Fixtures e helpers compartilhados com a suíte de pagamento.
from apps.sgd.tests.test_arlo_integration import storage_local  # noqa: F401
from apps.sgd.tests.test_registro_pagamento import CAMINHOS, _pagar, aprovadores, autorizada  # noqa: F401
from apps.sgp.models import GlosaRisk
from apps.sgp.models.activity import Activity

pytestmark = pytest.mark.django_db

SEM_EVIDENCIA = "concluido_sem_evidencia"
RISCOS = GlosaRisk.objects.filter(tipo_situacao=GlosaRisk.Tipo.DEMANDA_SEM_EVIDENCIA)
_PAPEL_DE_RUNTIME = "sgd_glosa_evidencia_runtime"


def _deixar_sem_evidencia(demand):
    """Direto no banco, sem passar pelo signal: aqui importa só o estado da atividade."""
    Activity.objects.filter(pk=demand.activity_id).update(status=SEM_EVIDENCIA)
    demand.activity.refresh_from_db()


def _mudar_status(demand, status):
    atividade = Activity.objects.get(pk=demand.activity_id)
    atividade.status = status
    atividade.save(update_fields=["status"])


@contextmanager
def _sessao_de_adt(usuario_id):
    """O usuário dos testes ignora o RLS: aqui a escrita passa pela política, como em produção."""
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {_PAPEL_DE_RUNTIME} NOLOGIN NOBYPASSRLS;")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"GRANT INSERT ON sgp_glosarisk TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {_PAPEL_DE_RUNTIME};")
        cursor.execute(f"SET LOCAL ROLE {_PAPEL_DE_RUNTIME};")
        cursor.execute("SELECT set_config('app.user_role', 'adt-acr', true)")
        cursor.execute("SELECT set_config('app.current_user_id', %s, true)", [str(usuario_id)])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE;")


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
    def test_registra_as_concluidas_sem_esperar_o_commit(self, autorizada, usuario_fgd):  # noqa: F811
        """A transação do teste nunca confirma: o risco não depende de `on_commit` nem do broker."""
        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)
        aberta = DemandFactory(activity=autorizada.activity, status="submetida")

        _mudar_status(autorizada, SEM_EVIDENCIA)

        risco = RISCOS.get()
        assert risco.demanda_id == str(autorizada.pk)
        assert risco.valor_exposto == Decimal("800.00")
        assert not RISCOS.filter(demanda_id=str(aberta.pk)).exists()

    def test_salvar_de_novo_nao_duplica(self, autorizada, usuario_fgd):  # noqa: F811
        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)

        _mudar_status(autorizada, SEM_EVIDENCIA)
        _mudar_status(autorizada, SEM_EVIDENCIA)

        assert RISCOS.count() == 1

    def test_outro_status_nao_registra(self, autorizada, usuario_fgd):  # noqa: F811
        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)

        _mudar_status(autorizada, "em_andamento")

        assert not RISCOS.exists()

    def test_sem_demanda_concluida_nao_registra(self, autorizada):  # noqa: F811
        _mudar_status(autorizada, SEM_EVIDENCIA)

        assert not RISCOS.exists()

    def test_tecnico_que_fecha_a_atividade_registra_a_demanda_de_outro_solicitante(
        self, autorizada, usuario_fgd,  # noqa: F811
    ):
        _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)
        tecnico = UserFactory()

        with _sessao_de_adt(tecnico.pk):
            assert not Demand.objects.filter(pk=autorizada.pk).exists()
            registradas = workflow_service.registrar_riscos_da_atividade_sem_evidencia(autorizada.activity_id)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.user_role', true)")
                assert cursor.fetchone()[0] == "adt-acr"

        assert registradas == 1
        assert RISCOS.get().demanda_id == str(autorizada.pk)


def test_registrar_de_novo_mantem_o_primeiro_registro(autorizada, usuario_fgd):  # noqa: F811
    _pagar("tela", autorizada, Decimal("800.00"), usuario_fgd)
    autorizada.refresh_from_db()

    workflow_service.registrar_demanda_sem_evidencia(autorizada, usuario=usuario_fgd)
    autorizada.valor_pago_total = Decimal("1.00")
    workflow_service.registrar_demanda_sem_evidencia(autorizada)

    risco = RISCOS.get()
    assert (risco.valor_exposto, risco.criado_por) == (Decimal("800.00"), usuario_fgd)
