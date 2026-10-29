from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.sgd.exceptions import ErroDeDominio, JustificativaObrigatoria, RegraDeNegocio
from apps.sgd.models.demand import Demand
from apps.sgd.services import balance as balance_service
from apps.sgd.services.approval import demand_visibility_scope, preview_impacto
from apps.sgd.services.workflow import executar_transicao
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
    with pytest.raises(JustificativaObrigatoria):
        executar_transicao(demand_rascunho_rn, "devolvida", ator=usuario_articulador_rn, justificativa="")


def test_autorizar_excedente_sem_justificativa_bloqueia(
    demand_request_rn, solicitante_rn, usuario_ugp, allocation_territorial_rn, limite_individual_rn,
):
    """RF16: excedente_autorizado=True bypassa o limite individual — exige
    justificativa como qualquer outra decisão que se desvia do padrão."""
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])

    with pytest.raises(ErroDeDominio):
        executar_transicao(
            demand, "autorizada", ator=usuario_ugp,
            ajustes={demand_request_rn.pk: limite_individual_rn.valor_limite + Decimal("1")},
            excedente_autorizado=True, justificativa="",
        )


def test_preview_decisao_retorna_semaforo(demand_request_rn, allocation_territorial_rn, limite_individual_rn):
    preview = preview_impacto(demand_request_rn, Decimal("4600"))
    assert preview["individual"]["semaforo_apos"] in {"verde", "amarelo", "vermelho"}
    assert preview["territorial"]["semaforo_apos"] in {"verde", "amarelo", "vermelho"}


def test_preview_decisao_nao_conta_reserva_ja_feita_em_dobro(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    """A solicitação já está reservada pelo valor estimado — perguntar o
    preview pelo mesmo valor não pode mudar a faixa nem bloquear (antes
    contava o valor inteiro de novo, por cima da própria reserva)."""
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand_request_rn.valor_autorizado = demand_request_rn.valor_estimado
    demand_request_rn.save(update_fields=["valor_autorizado"])

    preview = preview_impacto(demand_request_rn, demand_request_rn.valor_estimado)

    assert preview["disponivel"] is True
    assert preview["trava_bloqueada"] is None
    assert preview["individual"]["semaforo_apos"] == preview["individual"]["semaforo_antes"]


@pytest.fixture
def solicitante_rn_sem_nivel(solicitante_rn):
    """ADT com perfil global: o motor não resolve um único nível para ele."""
    solicitante_rn.profiles.update(territorio=None)
    return solicitante_rn


@pytest.mark.parametrize("valor", [Decimal("1500"), Decimal("500")], ids=["aumento", "reducao"])
def test_preview_decisao_com_solicitante_sem_nivel_e_regra_de_negocio(
    demand_request_rn, solicitante_rn_sem_nivel, allocation_territorial_rn, valor,
):
    """Quem decide tem acesso; o que falta é o nível do solicitante."""
    with pytest.raises(RegraDeNegocio) as excinfo:
        preview_impacto(demand_request_rn, valor)

    assert excinfo.value.mensagem.startswith("Não há como conferir o pool territorial do solicitante.")


def test_autorizar_com_ajuste_nao_depende_do_nivel_atual_do_solicitante(
    demand_request_rn, solicitante_rn, usuario_ugp, allocation_territorial_rn, limite_individual_rn,
):
    """O perfil do solicitante muda depois da reserva: o ajuste continua na
    alocação reservada, sem negar acesso a quem decide."""
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    solicitante_rn.profiles.update(territorio=None)

    executar_transicao(demand, "autorizada", ator=usuario_ugp, ajustes={demand_request_rn.pk: Decimal("1200")})

    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == Decimal("1200")


def test_articulador_nao_pode_pre_autorizar_a_propria_demanda(activity_rn, usuario_articulador_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=usuario_articulador_rn, status="submetida")

    with pytest.raises(PermissionDenied):
        executar_transicao(demand, "pre_autorizada", ator=usuario_articulador_rn)


def test_articulador_de_outro_estado_nao_pode_pre_autorizar(activity_rn, usuario_articulador_ce):
    demand = DemandFactory(activity=activity_rn, status="submetida")

    with pytest.raises(PermissionDenied):
        executar_transicao(demand, "pre_autorizada", ator=usuario_articulador_ce)


def test_articulador_nao_pode_devolver_a_propria_demanda(activity_rn, usuario_articulador_rn):
    demand = DemandFactory(activity=activity_rn, solicitante=usuario_articulador_rn, status="submetida")

    with pytest.raises(PermissionDenied):
        executar_transicao(demand, "devolvida", ator=usuario_articulador_rn, justificativa="Corrigir.")


def test_autorizar_com_ajuste_de_id_de_outra_demanda_rejeitado(
    demand_request_rn, solicitante_rn, usuario_ugp, allocation_territorial_rn, limite_individual_rn,
):
    """Um `demand_request_id` em `ajustes` que não pertence à demanda sendo
    autorizada era ignorado em silêncio — agora vira 400."""
    demand = demand_request_rn.demanda
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)
    demand.status = "pre_autorizada"
    demand.save(update_fields=["status"])
    id_inexistente = demand_request_rn.pk + 10_000

    with pytest.raises(ErroDeDominio):
        executar_transicao(demand, "autorizada", ator=usuario_ugp, ajustes={id_inexistente: Decimal("100")})


def test_ugp_nao_pode_fazer_transicao_de_outro_perfil(usuario_ugp, activity_rn):
    demand = DemandFactory(activity=activity_rn, status="submetida")

    with pytest.raises(PermissionDenied):
        executar_transicao(demand, "pre_autorizada", ator=usuario_ugp)
    demand.refresh_from_db()
    assert demand.status == "submetida"


def test_quem_nao_e_o_solicitante_nao_submete(demand_request_rn, usuario_ugp):
    with pytest.raises(PermissionDenied):
        executar_transicao(demand_request_rn.demanda, "submetida", ator=usuario_ugp)


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


@pytest.mark.parametrize("cliente", ["auth_client_solicitante", "auth_client_super_admin"])
def test_adt_e_super_admin_criam_demanda(request, cliente, activity_rn):
    client = request.getfixturevalue(cliente)

    response = client.post(
        "/api/v1/sgd/demandas/", {"titulo": "Diárias para oficina", "activity_id": activity_rn.pk}, format="json",
    )

    assert response.status_code == 201
    assert Demand.objects.filter(activity=activity_rn).count() == 1


@pytest.mark.parametrize(
    "cliente", ["auth_client_articulador_rn", "auth_client_ugp", "auth_client_fgd"],
)
def test_quem_decide_nao_cria_demanda(request, cliente, activity_rn):
    """SGD §1 / Core §2.1: Articulador pré-autoriza, UGP autoriza e FGD
    atende — nenhum deles cria demanda (e por isso não aprova a própria)."""
    client = request.getfixturevalue(cliente)

    response = client.post(
        "/api/v1/sgd/demandas/", {"titulo": "Diárias para oficina", "activity_id": activity_rn.pk}, format="json",
    )

    assert response.status_code == 403
    assert not Demand.objects.filter(activity=activity_rn).exists()
