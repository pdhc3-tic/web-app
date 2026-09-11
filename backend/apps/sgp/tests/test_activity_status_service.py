"""
Testes de apps.sgp.services.activity_status.

Cobre a regra de transição de status de Activity e os três pontos que a
aplicam: API web (ActivityDetailSerializer), Django Admin (ActivityAdminForm)
e sync do SCA (ActivitySyncEntity).
"""
import datetime
from unittest.mock import patch

import pytest
from django.forms.models import model_to_dict
from rest_framework import status

from apps.sca.sync_entities import ActivitySyncEntity, SyncEntityError
from apps.sgp.admin import ActivityAdminForm
from apps.sgp.models import Activity
from apps.sgp.services.activity_status import (
    EvidenciaObrigatoriaError,
    JustificativaObrigatoriaError,
    NovaDataObrigatoriaError,
    TransicaoInvalidaError,
    transition,
    validar_transicao,
)
from apps.sgp.tests.factories import ActivityFactory


# ===========================================================================
# validar_transicao() / transition() — regras puras
# ===========================================================================

@pytest.mark.django_db
def test_transicao_valida(municipio_rn):
    """planejado → agendado é uma transição permitida."""
    atividade = ActivityFactory(municipio=municipio_rn, status="planejado")
    transition(atividade, "agendado", usuario=None)
    assert atividade.status == "agendado"


@pytest.mark.django_db
def test_transicao_invalida(municipio_rn):
    """planejado → concluido não está em STATUS_TRANSITIONS."""
    atividade = ActivityFactory(municipio=municipio_rn, status="planejado")
    with pytest.raises(TransicaoInvalidaError):
        validar_transicao(atividade, "concluido")


@pytest.mark.django_db
def test_terminal_nao_transiciona(municipio_rn):
    """Estado terminal (cancelada) não tem nenhuma transição permitida."""
    atividade = ActivityFactory(municipio=municipio_rn, status="cancelada")
    with pytest.raises(TransicaoInvalidaError):
        validar_transicao(atividade, "agendado")


@pytest.mark.django_db
def test_concluido_exige_evidencia(municipio_rn):
    """has_evidencias() False bloqueia a conclusão."""
    atividade = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    with pytest.raises(EvidenciaObrigatoriaError):
        validar_transicao(atividade, "concluido")


@pytest.mark.django_db
def test_concluido_com_foto_passa(municipio_rn):
    """has_evidencias() True (1 foto ativa) libera a conclusão."""
    atividade = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    with patch.object(Activity, "has_evidencias", return_value=True):
        validar_transicao(atividade, "concluido")  # não levanta


@pytest.mark.django_db
def test_justificativa_obrigatoria(municipio_rn):
    """cancelada e nao_realizada sem justificativa levantam erro."""
    cancelando = ActivityFactory(municipio=municipio_rn, status="agendado")
    with pytest.raises(JustificativaObrigatoriaError):
        validar_transicao(cancelando, "cancelada")

    nao_realizando = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    with pytest.raises(JustificativaObrigatoriaError):
        validar_transicao(nao_realizando, "nao_realizada")

    # com justificativa, a mesma transição passa
    validar_transicao(cancelando, "cancelada", justificativa="Falta de recursos.")


@pytest.mark.django_db
def test_adiada_exige_nova_data(municipio_rn):
    """Reagendar (adiada → agendado) exige data_inicio nova, diferente da atual."""
    atividade = ActivityFactory(municipio=municipio_rn, status="adiada")

    with pytest.raises(NovaDataObrigatoriaError):
        validar_transicao(atividade, "agendado")  # sem nova_data

    with pytest.raises(NovaDataObrigatoriaError):
        validar_transicao(atividade, "agendado", nova_data=atividade.data_inicio)  # mesma data

    nova_data = atividade.data_inicio + datetime.timedelta(days=7)
    validar_transicao(atividade, "agendado", nova_data=nova_data)  # não levanta

    # adiada → cancelada não precisa de nova data (só cancela)
    validar_transicao(atividade, "cancelada", justificativa="Atividade cancelada.")


# ===========================================================================
# SCA — o sync não consegue burlar a regra
# ===========================================================================

@pytest.mark.django_db
def test_sca_nao_burla_evidencia(municipio_rn):
    """ActivitySyncEntity.apply_changes() não grava 'concluido' sem evidência."""
    atividade = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    entity = ActivitySyncEntity()

    with pytest.raises(SyncEntityError, match="EVIDENCIA_OBRIGATORIA"):
        entity.apply_changes(atividade, {"status": "concluido"})

    atividade.refresh_from_db()
    assert atividade.status == "em_andamento"


# ===========================================================================
# Admin — o form não consegue burlar a regra
# ===========================================================================

@pytest.mark.django_db
def test_admin_nao_burla_evidencia(municipio_rn):
    """ActivityAdminForm.clean() bloqueia 'concluido' sem evidência, igual à API web."""
    atividade = ActivityFactory(municipio=municipio_rn, status="em_andamento")
    dados_form = model_to_dict(atividade)
    dados_form["status"] = "concluido"

    form = ActivityAdminForm(data=dados_form, instance=atividade)

    assert not form.is_valid()
    assert "status" in form.errors

    atividade.refresh_from_db()
    assert atividade.status == "em_andamento"


# ===========================================================================
# API web — mesmos status HTTP e mensagens de antes da extração
# ===========================================================================

@pytest.mark.django_db
def test_api_web_inalterada(ugp_client, municipio_rn):
    """PATCH planejado → concluido pela API continua 400 com a mesma mensagem."""
    atividade = ActivityFactory(municipio=municipio_rn, status="planejado")

    response = ugp_client.patch(
        f"/api/v1/sgp/atividades/{atividade.pk}/",
        data={"status": "concluido"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    resposta_str = str(response.data)
    assert "VALIDATION_ERROR" in resposta_str or "Transição inválida" in resposta_str
