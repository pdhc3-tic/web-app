"""Issue #352: a abrangência da demanda é o território do SOLICITANTE, congelado
na criação, e não o estado da atividade.

Cenário PB/RN: o ADT do território X (sede na PB) vincula uma atividade num
município do RN que também pertence a X. A demanda vai para o Articulador da
PB, reserva do pool de X e sinaliza `atividade_fora_do_territorio`."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import UserProfile
from apps.core.tests.factories import (
    MunicipalityFactory,
    RoleFactory,
    StateFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgd.models import Demand
from apps.sgd.serializers.demand import DemandSerializer
from apps.sgd.services import demand as demand_service
from apps.sgd.services.approval import demand_visibility_scope, demandas_aguardando_acao
from apps.sgd.services import recurso_extra as recurso_extra_service
from apps.sgd.tests.factories import (
    BudgetIncreaseRequestFactory,
    DemandRequestFactory,
)
from apps.sgd.views.remanejamento import pedidos_visiveis
from apps.sgp.tests.factories import ActivityFactory, BudgetPoolFactory, SpendingLimitFactory, WorkPlanAcaoFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def territorio_x(db):
    return TerritoryFactory(nome="Território X", estados=["PB"])


@pytest.fixture
def municipio_rn_no_territorio_x(db, territorio_x):
    return MunicipalityFactory(
        nome="Município RN em X", state=StateFactory(sigla="RN", nome="Rio Grande do Norte"),
        territory=territorio_x, codigo_ibge="2400999",
    )


@pytest.fixture
def adt_x(db, territorio_x):
    return UserFactory(
        email="adt.x@test.com", nome="ADT X",
        profiles=[(RoleFactory(slug="adt-acr", nome="ADT / ACR"), territorio_x)],
    )


@pytest.fixture
def articulador_pb(db, territorio_x):
    return UserFactory(
        email="articulador.pb@test.com", nome="Articulador PB",
        profiles=[(RoleFactory(slug="articulador-estadual", nome="Articulador Estadual"), territorio_x)],
    )


@pytest.fixture
def activity_no_rn(db, municipio_rn_no_territorio_x, adt_x):
    return ActivityFactory(
        municipio=municipio_rn_no_territorio_x, tecnico_responsavel=adt_x, status="planejado",
        acao=WorkPlanAcaoFactory(),
    )


def _criar(activity, solicitante) -> Demand:
    return demand_service.criar_demanda(
        titulo="Demanda PB/RN", activity=activity, justificativa="", solicitante=solicitante,
    )


def test_criacao_grava_territorio_do_solicitante(activity_no_rn, adt_x, territorio_x):
    demand = _criar(activity_no_rn, adt_x)

    assert demand.territorio_id == territorio_x.pk
    assert demand.estado_sigla == "PB"
    dados = DemandSerializer(demand).data
    assert dados["estado_sigla"] == "PB"
    assert dados["territorio"] == territorio_x.pk
    assert dados["atividade_fora_do_territorio"] is True
    assert dados["contexto"]["territorio_id"] == territorio_x.pk


def test_atividade_no_proprio_estado_nao_esta_fora(activity_rn, solicitante_rn):
    demand = _criar(activity_rn, solicitante_rn)

    assert demand.estado_sigla == "RN"
    assert DemandSerializer(demand).data["atividade_fora_do_territorio"] is False


def test_territorio_multiestado_usa_o_estado_sede_onde_quer_que_a_atividade_aconteca(db):
    territorio = TerritoryFactory(nome="Território PB/RN", estados=["PB", "RN"])
    adt = UserFactory(email="adt.pbrn@test.com", profiles=[(RoleFactory(slug="adt-acr"), territorio)])
    municipio = MunicipalityFactory(state=StateFactory(sigla="RN"), territory=territorio, codigo_ibge="2400998")
    activity = ActivityFactory(municipio=municipio, tecnico_responsavel=adt, status="planejado",
                               acao=WorkPlanAcaoFactory())

    demand = _criar(activity, adt)

    assert demand.estado_sigla == "PB"
    assert demand.territorio_id == territorio.pk
    assert DemandSerializer(demand).data["atividade_fora_do_territorio"] is True


@patch("apps.core.tasks.notifications.send_email_notification.delay")
def test_cenario_pb_rn_fila_notificacao_e_pool(
    mocked_delay, activity_no_rn, adt_x, territorio_x, articulador_pb, usuario_articulador_rn,
    rubrica_diarias, territory_rn,
):
    pool_x = BudgetPoolFactory(
        rubrica=rubrica_diarias, territorio=territorio_x,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )
    pool_rn = BudgetPoolFactory(
        rubrica=rubrica_diarias, territorio=territory_rn,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )
    SpendingLimitFactory(user=adt_x, rubrica=rubrica_diarias, valor_limite=5_000)
    demand = _criar(activity_no_rn, adt_x)
    DemandRequestFactory(demanda=demand, tipo="diaria", rubrica=rubrica_diarias, valor_estimado=1_000)

    demand_service.submeter_demanda(demand, usuario=adt_x)

    fila_pb = demandas_aguardando_acao(articulador_pb, Demand.objects.all())
    fila_rn = demandas_aguardando_acao(usuario_articulador_rn, Demand.objects.all())
    assert demand.pk in set(fila_pb.values_list("pk", flat=True))
    assert demand.pk not in set(fila_rn.values_list("pk", flat=True))
    assert not Demand.objects.filter(demand_visibility_scope(usuario_articulador_rn)).filter(pk=demand.pk).exists()

    assert articulador_pb.notifications.filter(evento="demand_submetida").exists()
    assert not usuario_articulador_rn.notifications.filter(evento="demand_submetida").exists()

    pool_x.refresh_from_db()
    pool_rn.refresh_from_db()
    assert pool_x.valor_comprometido == Decimal("1000")
    assert pool_rn.valor_comprometido == Decimal("0")


def test_mudar_lotacao_do_solicitante_nao_move_a_demanda(
    activity_no_rn, adt_x, territorio_x, territory_rn, articulador_pb, usuario_articulador_rn,
):
    demand = _criar(activity_no_rn, adt_x)
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    UserProfile.objects.filter(user=adt_x).update(territorio=territory_rn)

    demand.refresh_from_db()
    assert demand.territorio_id == territorio_x.pk
    assert demand.estado_sigla == "PB"
    assert demandas_aguardando_acao(articulador_pb, Demand.objects.all()).filter(pk=demand.pk).exists()
    assert not demandas_aguardando_acao(usuario_articulador_rn, Demand.objects.all()).filter(pk=demand.pk).exists()


def test_solicitante_sem_territorio_cria_demanda_nacional(activity_rn, usuario_articulador_rn):
    super_admin = UserFactory(
        email="super@test.com", profiles=[(RoleFactory(slug="super-admin", nome="Super Admin"), None)],
    )

    demand = _criar(activity_rn, super_admin)
    demand.status = "submetida"
    demand.save(update_fields=["status"])

    assert demand.estado_sigla is None
    assert demand.territorio_id is None
    assert DemandSerializer(demand).data["atividade_fora_do_territorio"] is False
    # Nenhum Articulador recebe a demanda nacional, nem o de perfil global.
    articulador_global = UserFactory(
        email="articulador.global@test.com",
        profiles=[(RoleFactory(slug="articulador-estadual"), None)],
    )
    for articulador in (usuario_articulador_rn, articulador_global):
        assert not demandas_aguardando_acao(articulador, Demand.objects.all()).filter(pk=demand.pk).exists()


def test_recurso_extra_da_demanda_segue_o_territorio_da_demanda(
    activity_no_rn, adt_x, territorio_x, articulador_pb, usuario_articulador_rn, rubrica_diarias, territory_rn,
):
    """O pedido de recurso extra vinculado à demanda vai para o Articulador e o
    pool do território congelado na demanda, não da atividade nem do perfil atual."""
    pool_x = BudgetPoolFactory(
        rubrica=rubrica_diarias, territorio=territorio_x,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )
    BudgetPoolFactory(
        rubrica=rubrica_diarias, territorio=territory_rn,
        valor_alocado=10_000, valor_comprometido=0, valor_executado=0,
    )
    demand = _criar(activity_no_rn, adt_x)
    pedido = BudgetIncreaseRequestFactory(
        user=adt_x, rubrica=rubrica_diarias, activity=activity_no_rn, demanda_id=str(demand.pk),
    )
    UserProfile.objects.filter(user=adt_x).update(territorio=territory_rn)

    assert recurso_extra_service._sigla_do_pedido(pedido) == "PB"
    assert pedidos_visiveis(articulador_pb).filter(pk=pedido.pk).exists()
    assert not pedidos_visiveis(usuario_articulador_rn).filter(pk=pedido.pk).exists()
    destino, _ = recurso_extra_service._travar_pools(pedido, None)
    assert destino.pk == pool_x.pk
