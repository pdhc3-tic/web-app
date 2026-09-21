from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.models.demand import Demand
from apps.sgd.services import balance as balance_service
from apps.sgd.services.approval import autorizar, demand_visibility_scope, devolver, preview_impacto
from apps.sgd.tests.factories import DemandFactory

pytestmark = pytest.mark.django_db


def test_articulador_nao_ve_demandas_de_outro_estado(activity_rn, usuario_articulador_ce):
    DemandFactory(activity=activity_rn, status="submetida")

    scope = demand_visibility_scope(usuario_articulador_ce)
    qs = Demand.objects.filter(scope) if scope is not None else Demand.objects.all()
    assert qs.count() == 0


def test_articulador_ve_demandas_do_proprio_estado(activity_rn, usuario_articulador_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")

    scope = demand_visibility_scope(usuario_articulador_rn)
    qs = Demand.objects.filter(scope) if scope is not None else Demand.objects.all()
    assert demand in qs


def test_ugp_ve_demandas_de_qualquer_territorio(usuario_ugp):
    assert demand_visibility_scope(usuario_ugp) is None


def test_devolver_sem_justificativa_bloqueia(demand_rascunho_rn, usuario_articulador_rn):
    demand_rascunho_rn.status = "submetida"
    demand_rascunho_rn.save(update_fields=["status"])
    with pytest.raises(Exception):
        devolver(demand_rascunho_rn, responsavel=usuario_articulador_rn, justificativa="")


def test_autorizar_excedente_sem_justificativa_bloqueia(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """RF16: excedente_autorizado=True bypassa o limite individual — exige
    justificativa como qualquer outra decisão que se desvia do padrão."""
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])

    with pytest.raises(DRFValidationError):
        autorizar(
            demand, responsavel=solicitante_rn,
            ajustes={demand_request_rn.pk: limite_individual_rn.valor_limite + Decimal("1")},
            excedente_autorizado=True, justificativa="",
        )


def test_autorizar_excedente_com_justificativa_autoriza_sem_elevar_limite(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    valor_limite_antes = limite_individual_rn.valor_limite
    novo_valor = valor_limite_antes + Decimal("1")

    autorizar(
        demand, responsavel=solicitante_rn, ajustes={demand_request_rn.pk: novo_valor},
        excedente_autorizado=True, justificativa="Demanda urgente aprovada pela UGP.",
    )

    demand_request_rn.refresh_from_db()
    assert demand_request_rn.valor_autorizado == novo_valor
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == valor_limite_antes

    ultimo_step = demand.etapas.latest("criado_em")
    assert ultimo_step.excedente_autorizado is True
    assert ultimo_step.justificativa == "Demanda urgente aprovada pela UGP."


def test_preview_decisao_retorna_semaforo(demand_request_rn, allocation_territorial_rn, limite_individual_rn):
    preview = preview_impacto(demand_request_rn, Decimal("4600"))
    assert preview["individual"]["semaforo_apos"] in {"verde", "amarelo", "vermelho"}
    assert preview["territorial"]["semaforo_apos"] in {"verde", "amarelo", "vermelho"}


def test_articulador_nao_ve_demanda_em_rascunho_de_outro_solicitante_no_proprio_estado(
    activity_rn, usuario_articulador_rn,
):
    DemandFactory(activity=activity_rn, status="rascunho")

    scope = demand_visibility_scope(usuario_articulador_rn)
    qs = Demand.objects.filter(scope) if scope is not None else Demand.objects.all()
    assert qs.count() == 0


def test_articulador_mantem_acesso_a_demanda_que_ja_decidiu(activity_rn, usuario_articulador_rn):
    from apps.sgd.models.approval_step import ApprovalStep

    demand = DemandFactory(activity=activity_rn, status="pre_autorizada")
    ApprovalStep.objects.create(
        demanda=demand, etapa="pre_autorizacao", responsavel=usuario_articulador_rn, acao="aprovado",
    )

    scope = demand_visibility_scope(usuario_articulador_rn)
    qs = Demand.objects.filter(scope) if scope is not None else Demand.objects.all()
    assert demand in qs


def test_api_autorizar_rejeita_usuario_sem_role_ugp(auth_client_articulador_rn, demand_rascunho_rn):
    demand_rascunho_rn.status = "pre_autorizada"
    demand_rascunho_rn.save(update_fields=["status"])

    response = auth_client_articulador_rn.post(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/autorizar/", {})

    assert response.status_code == 403


def test_api_pre_autorizar_rejeita_usuario_sem_role_articulador(auth_client_ugp, demand_rascunho_rn):
    demand_rascunho_rn.status = "submetida"
    demand_rascunho_rn.save(update_fields=["status"])

    response = auth_client_ugp.post(f"/api/v1/sgd/demandas/{demand_rascunho_rn.pk}/pre-autorizar/", {})

    assert response.status_code == 403
