"""Desativar um usuário cancela as demandas não autorizadas dele, pelo workflow, e libera o saldo."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.db import connection
from django.test import RequestFactory
from freezegun import freeze_time

from apps.core.admin import UserAdmin
from apps.core.models import AuditLog, User
from apps.core.models.notifications import Notification
from apps.core.serializers import UserDetailSerializer
from apps.core.services.usuarios import desativar
from apps.sgd.exceptions import TransicaoInvalida
from apps.sgd.models import Demand
from apps.sgd.services import workflow as workflow_service
from apps.sgd.tests.factories import DemandFactory, DemandRequestFactory
from apps.sgp.budget import limites
from apps.sgp.models import BudgetTransaction, SpendingLimit
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, SpendingLimitFactory

pytestmark = pytest.mark.django_db

CANCELAVEIS = ["rascunho", "submetida", "devolvida", "pre_autorizada"]
FALHA_NO_CANCELAMENTO = "apps.sgd.services.desativacao.cancelar_demandas_do_usuario"

_CAMINHO = {
    "rascunho": [],
    "submetida": ["submetida"],
    "devolvida": ["submetida", "devolvida"],
    "pre_autorizada": ["submetida", "pre_autorizada"],
    "autorizada": ["submetida", "pre_autorizada", "autorizada"],
    "em_atendimento": ["submetida", "pre_autorizada", "autorizada", "em_atendimento"],
    "concluida": ["submetida", "pre_autorizada", "autorizada", "em_atendimento", "concluida"],
}
_QUEM_FAZ = {
    "submetida": "solicitante",
    "devolvida": "articulador",
    "pre_autorizada": "articulador",
    "autorizada": "ugp",
    "em_atendimento": "fgd",
    "concluida": "fgd",
}


@pytest.fixture(autouse=True)
def sem_envio_de_email():
    with patch("apps.core.tasks.notifications.send_email_notification.delay"):
        yield


@pytest.fixture
def atores(solicitante_rn, usuario_articulador_rn, usuario_ugp, usuario_fgd):
    return {"solicitante": solicitante_rn, "articulador": usuario_articulador_rn, "ugp": usuario_ugp, "fgd": usuario_fgd}


def _levar(demand, status, atores):
    for destino in _CAMINHO[status]:
        dados = {}
        if destino == "devolvida":
            dados["justificativa"] = "Motivo."
        if destino == "concluida":
            dados["valores_pagos"] = {s.pk: s.valor_estimado for s in demand.solicitacoes.all()}
        workflow_service.executar_transicao(demand, destino, ator=atores[_QUEM_FAZ[destino]], **dados)
    return demand


def _demanda(status, *, activity, solicitante, rubrica, atores, valor=1_000):
    demand = DemandFactory(activity=activity, solicitante=solicitante, status="rascunho")
    DemandRequestFactory(demanda=demand, tipo="diaria", rubrica=rubrica, valor_estimado=valor)
    return _levar(demand, status, atores)


@pytest.fixture
def nova_demanda(activity_rn, solicitante_rn, rubrica_diarias, atores, allocation_territorial_rn, limite_individual_rn):
    def criar(status, valor=1_000, rubrica=rubrica_diarias):
        return _demanda(
            status, activity=activity_rn, solicitante=solicitante_rn, rubrica=rubrica, atores=atores, valor=valor,
        )
    return criar


# ── Saldo ────────────────────────────────────────────────────────────────────

def test_comprometido_fica_igual_a_soma_das_autorizadas_e_em_atendimento(
    nova_demanda, solicitante_rn, usuario_super_admin, limite_individual_rn, allocation_territorial_rn,
):
    for status, valor in [
        ("rascunho", 100), ("submetida", 200), ("devolvida", 300), ("pre_autorizada", 400),
        ("autorizada", 500), ("em_atendimento", 600),
    ]:
        nova_demanda(status, valor=valor)
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("2000")

    desativar(solicitante_rn, por=usuario_super_admin)

    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("1100")
    assert allocation_territorial_rn.valor_comprometido == Decimal("1100")


@pytest.mark.parametrize("status", CANCELAVEIS)
def test_cancela_as_nao_autorizadas(status, nova_demanda, solicitante_rn, usuario_super_admin):
    demand = nova_demanda(status)

    canceladas = desativar(solicitante_rn, por=usuario_super_admin)

    assert [d.pk for d in canceladas] == [demand.pk]
    demand.refresh_from_db()
    assert demand.status == "cancelada"
    assert demand.solicitacoes.get().valor_reservado == 0
    solicitante_rn.refresh_from_db()
    assert solicitante_rn.ativo is False


@pytest.mark.parametrize("status", ["autorizada", "em_atendimento", "concluida"])
def test_autorizadas_em_diante_seguem_o_fluxo_normal(
    status, nova_demanda, solicitante_rn, usuario_super_admin, limite_individual_rn, allocation_territorial_rn,
):
    demand = nova_demanda(status)
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    antes = (
        limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado,
        allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado,
    )

    assert desativar(solicitante_rn, por=usuario_super_admin) == []

    demand.refresh_from_db()
    assert demand.status == status
    limite_individual_rn.refresh_from_db()
    allocation_territorial_rn.refresh_from_db()
    assert antes == (
        limite_individual_rn.valor_comprometido, limite_individual_rn.valor_executado,
        allocation_territorial_rn.valor_comprometido, allocation_territorial_rn.valor_executado,
    )


def test_rascunho_sem_reserva_nao_gera_movimento_no_ledger(
    nova_demanda, solicitante_rn, usuario_super_admin,
):
    nova_demanda("rascunho")

    desativar(solicitante_rn, por=usuario_super_admin)

    assert not BudgetTransaction.objects.filter(tipo=BudgetTransaction.Tipo.LIBERACAO).exists()


def test_liberacao_no_ledger_registra_quem_desativou(
    nova_demanda, solicitante_rn, usuario_super_admin, limite_individual_rn, allocation_territorial_rn,
):
    nova_demanda("submetida")

    desativar(solicitante_rn, por=usuario_super_admin)

    liberacoes = BudgetTransaction.objects.filter(tipo=BudgetTransaction.Tipo.LIBERACAO)
    assert {(t.spending_limit_id, t.pool_id) for t in liberacoes} == {
        (limite_individual_rn.pk, None), (None, allocation_territorial_rn.pk),
    }
    assert {t.criado_por_id for t in liberacoes} == {usuario_super_admin.pk}
    assert {t.justificativa for t in liberacoes} == {"Solicitante desativado."}


def test_libera_reservas_de_mais_de_uma_rubrica(
    nova_demanda, solicitante_rn, usuario_super_admin, activity_rn, limite_individual_rn, allocation_territorial_rn,
):
    outra = BudgetRubricaFactory(slug="material", nome="Material")
    limite_outra = SpendingLimitFactory(user=solicitante_rn, rubrica=outra, valor_limite=5_000)
    pool_outra = BudgetPoolFactory(
        rubrica=outra, territorio=activity_rn.municipio.territory, valor_alocado=10_000,
    )
    nova_demanda("submetida", valor=300)
    nova_demanda("pre_autorizada", valor=700, rubrica=outra)

    desativar(solicitante_rn, por=usuario_super_admin)

    for linha in (limite_individual_rn, limite_outra, allocation_territorial_rn, pool_outra):
        linha.refresh_from_db()
        assert linha.valor_comprometido == 0


def test_libera_cada_reserva_da_linha_do_seu_periodo(
    activity_rn, solicitante_rn, rubrica_diarias, atores, usuario_super_admin, allocation_territorial_rn,
):
    SpendingLimit.objects.create(
        escopo=SpendingLimit.Escopo.PERFIL, perfil=solicitante_rn.profiles.get().perfil, rubrica=rubrica_diarias,
        valor_limite=Decimal("5000"), periodo_inicio=date(2026, 1, 1), periodo_fim=limites.FIM_EM_ABERTO,
    )
    comum = {"activity": activity_rn, "solicitante": solicitante_rn, "rubrica": rubrica_diarias, "atores": atores}
    with freeze_time("2026-11-03"):
        _demanda("submetida", valor=300, **comum)
    with freeze_time("2027-01-05"):
        _demanda("submetida", valor=700, **comum)
        linhas = SpendingLimit.objects.filter(user=solicitante_rn)
        assert sorted(linha.valor_comprometido for linha in linhas) == [Decimal("300"), Decimal("700")]

        desativar(solicitante_rn, por=usuario_super_admin)

    assert {linha.valor_comprometido for linha in linhas.all()} == {Decimal("0")}
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_comprometido == 0


def test_demanda_que_mudou_durante_a_operacao_desfaz_tudo(
    nova_demanda, solicitante_rn, usuario_super_admin, limite_individual_rn,
):
    demand = nova_demanda("submetida")

    with patch(FALHA_NO_CANCELAMENTO, side_effect=TransicaoInvalida("Mudou.")), pytest.raises(TransicaoInvalida):
        desativar(solicitante_rn, por=usuario_super_admin)

    assert User.objects.get(pk=solicitante_rn.pk).ativo is True
    demand.refresh_from_db()
    assert demand.status == "submetida"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == Decimal("1000")


def test_cancela_sem_contexto_de_sessao_com_o_papel_de_runtime(
    nova_demanda, solicitante_rn, usuario_super_admin, limite_individual_rn,
):
    """A suíte conecta como superusuário, que ignora o RLS: o teste troca para um papel
    sem BYPASSRLS, como um comando rodando fora de uma requisição."""
    demand = nova_demanda("submetida")
    with connection.cursor() as cursor:
        cursor.execute("CREATE ROLE sgd_desativacao_runtime NOLOGIN NOBYPASSRLS;")
        cursor.execute("GRANT USAGE ON SCHEMA public TO sgd_desativacao_runtime;")
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sgd_desativacao_runtime;")
        cursor.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sgd_desativacao_runtime;")
        cursor.execute("SET LOCAL ROLE sgd_desativacao_runtime;")
        cursor.execute("SELECT set_config('app.user_role', '', true)")
        cursor.execute("SELECT set_config('app.current_user_id', '', true)")
    try:
        desativar(solicitante_rn, por=usuario_super_admin)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE;")

    demand.refresh_from_db()
    assert demand.status == "cancelada"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == 0


def test_usuario_ja_inativo_nao_faz_nada(nova_demanda, solicitante_rn, usuario_super_admin):
    demand = nova_demanda("submetida")
    solicitante_rn.ativo = False
    solicitante_rn.save(update_fields=["ativo"])

    assert desativar(solicitante_rn, por=usuario_super_admin) == []

    demand.refresh_from_db()
    assert demand.status == "submetida"


# ── Notificação e auditoria ──────────────────────────────────────────────────

def test_notifica_so_o_articulador_do_estado_com_o_motivo_da_desativacao(
    nova_demanda, solicitante_rn, usuario_articulador_rn, usuario_articulador_ce, usuario_super_admin,
):
    nova_demanda("submetida")
    Notification.objects.all().delete()

    desativar(solicitante_rn, por=usuario_super_admin)

    notificacoes = Notification.objects.exclude(evento="demand_semaforo_mudou")
    assert {n.user_id for n in notificacoes} == {usuario_articulador_rn.pk}
    assert {n.evento for n in notificacoes} == {"demand_cancelada_automatico"}
    assert all("solicitante foi desativado" in n.mensagem for n in notificacoes)


def test_articulador_desativado_nao_notifica_a_si_mesmo(
    activity_rn, usuario_articulador_rn, usuario_super_admin,
):
    DemandFactory(activity=activity_rn, solicitante=usuario_articulador_rn, status="rascunho")

    desativar(usuario_articulador_rn, por=usuario_super_admin)

    assert not Notification.objects.filter(user=usuario_articulador_rn).exists()


def test_auditoria_registra_quem_desativou_e_as_demandas_canceladas(
    nova_demanda, solicitante_rn, usuario_super_admin,
):
    demand = nova_demanda("submetida")

    desativar(solicitante_rn, por=usuario_super_admin)

    log = AuditLog.objects.get(acao="user.deactivated", entidade_id=str(solicitante_rn.pk))
    assert log.user_id == usuario_super_admin.pk
    assert log.valores_novos == {"ativo": False, "demandas_canceladas": [demand.pk]}
    transicao = AuditLog.objects.filter(entidade="Demand", entidade_id=str(demand.pk)).latest("id")
    assert transicao.user_id == usuario_super_admin.pk
    assert transicao.valores_novos == {"status": "cancelada"}


# ── Caminhos de entrada ──────────────────────────────────────────────────────

def test_delete_desativa_e_cancela(auth_client_super_admin, nova_demanda, solicitante_rn):
    demand = nova_demanda("submetida")

    resposta = auth_client_super_admin.delete(f"/api/v1/users/{solicitante_rn.pk}/")

    assert resposta.status_code == 204
    demand.refresh_from_db()
    assert demand.status == "cancelada"


def test_delete_com_demanda_que_mudou_responde_400_e_mantem_o_usuario_ativo(
    auth_client_super_admin, nova_demanda, solicitante_rn,
):
    nova_demanda("submetida")

    with patch(FALHA_NO_CANCELAMENTO, side_effect=TransicaoInvalida("Mudou.")):
        resposta = auth_client_super_admin.delete(f"/api/v1/users/{solicitante_rn.pk}/")

    assert resposta.status_code == 400
    assert resposta.data["code"] == "INVALID_TRANSITION"
    assert User.objects.get(pk=solicitante_rn.pk).ativo is True


def test_patch_que_desativa_cancela_e_grava_os_outros_campos(
    auth_client_super_admin, nova_demanda, solicitante_rn,
):
    demand = nova_demanda("submetida")

    resposta = auth_client_super_admin.patch(
        f"/api/v1/users/{solicitante_rn.pk}/",
        {"ativo": False, "telefone": "84999990000", "email": "novo.adt@test.com"}, format="json",
    )

    assert resposta.status_code == 200
    assert resposta.data["ativo"] is False
    solicitante_rn.refresh_from_db()
    assert (solicitante_rn.ativo, solicitante_rn.telefone, solicitante_rn.email) == (
        False, "84999990000", "novo.adt@test.com",
    )
    demand.refresh_from_db()
    assert demand.status == "cancelada"


def test_edicao_com_dados_lidos_antes_nao_desfaz_a_desativacao(solicitante_rn):
    lido_antes = User.objects.get(pk=solicitante_rn.pk)
    User.objects.filter(pk=solicitante_rn.pk).update(ativo=False)

    serializer = UserDetailSerializer(lido_antes, data={"telefone": "84999990000"}, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    solicitante_rn.refresh_from_db()
    assert (solicitante_rn.ativo, solicitante_rn.telefone) == (False, "84999990000")


def test_patch_que_nao_desativa_nao_cancela(auth_client_super_admin, nova_demanda, solicitante_rn):
    demand = nova_demanda("submetida")

    resposta = auth_client_super_admin.patch(
        f"/api/v1/users/{solicitante_rn.pk}/", {"ativo": True, "telefone": "84999990000"}, format="json",
    )

    assert resposta.status_code == 200
    demand.refresh_from_db()
    assert demand.status == "submetida"


def test_reativar_nao_restaura_as_demandas_canceladas(
    auth_client_super_admin, nova_demanda, solicitante_rn, limite_individual_rn,
):
    demand = nova_demanda("submetida")
    auth_client_super_admin.delete(f"/api/v1/users/{solicitante_rn.pk}/")

    resposta = auth_client_super_admin.patch(
        f"/api/v1/users/{solicitante_rn.pk}/?ativo=false", {"ativo": True}, format="json",
    )

    assert resposta.status_code == 200
    solicitante_rn.refresh_from_db()
    assert solicitante_rn.ativo is True
    demand.refresh_from_db()
    assert demand.status == "cancelada"
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_comprometido == 0


def _salvar_no_admin(usuario, *, por, changed_data):
    request = RequestFactory().post("/admin/core/user/")
    request.user = por
    modelo_admin = UserAdmin(User, admin.site)
    with patch.object(UserAdmin, "message_user") as mensagem:
        modelo_admin.save_model(request, usuario, SimpleNamespace(changed_data=changed_data), True)
    return mensagem


def test_admin_que_desmarca_ativo_desativa_e_cancela(nova_demanda, solicitante_rn, usuario_super_admin):
    demand = nova_demanda("submetida")
    solicitante_rn.ativo = False

    _salvar_no_admin(solicitante_rn, por=usuario_super_admin, changed_data=["ativo"])

    assert User.objects.get(pk=solicitante_rn.pk).ativo is False
    demand.refresh_from_db()
    assert demand.status == "cancelada"


def test_admin_com_demanda_que_mudou_avisa_e_mantem_o_usuario_ativo(
    nova_demanda, solicitante_rn, usuario_super_admin,
):
    nova_demanda("submetida")
    solicitante_rn.ativo = False
    solicitante_rn.nome = "Outro nome"

    with patch(FALHA_NO_CANCELAMENTO, side_effect=TransicaoInvalida("Mudou.")):
        mensagem = _salvar_no_admin(solicitante_rn, por=usuario_super_admin, changed_data=["ativo"])

    mensagem.assert_called_once()
    salvo = User.objects.get(pk=solicitante_rn.pk)
    assert (salvo.ativo, salvo.nome) == (True, "Outro nome")


def test_admin_que_edita_outro_campo_nao_cancela(nova_demanda, solicitante_rn, usuario_super_admin):
    demand = nova_demanda("submetida")
    solicitante_rn.nome = "Outro nome"

    _salvar_no_admin(solicitante_rn, por=usuario_super_admin, changed_data=["nome"])

    demand.refresh_from_db()
    assert demand.status == "submetida"


# ── Impacto ──────────────────────────────────────────────────────────────────

def test_impacto_lista_o_que_a_desativacao_faria_sem_mudar_nada(
    auth_client_super_admin, nova_demanda, solicitante_rn, activity_rn, limite_individual_rn, rubrica_diarias,
):
    outra = BudgetRubricaFactory(slug="material", nome="Material")
    SpendingLimitFactory(user=solicitante_rn, rubrica=outra, valor_limite=5_000)
    BudgetPoolFactory(rubrica=outra, territorio=activity_rn.municipio.territory, valor_alocado=10_000)
    rascunho = nova_demanda("rascunho", valor=100)
    submetida = nova_demanda("submetida", valor=200)
    pre_autorizada = nova_demanda("pre_autorizada", valor=300, rubrica=outra)
    nova_demanda("autorizada", valor=400)

    resposta = auth_client_super_admin.get(f"/api/v1/core/usuarios/{solicitante_rn.pk}/impacto-desativacao/")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "demandas": [
            {"id": rascunho.pk, "titulo": rascunho.titulo, "status": "rascunho", "saldo_liberado": "0.00"},
            {"id": submetida.pk, "titulo": submetida.titulo, "status": "submetida", "saldo_liberado": "200.00"},
            {
                "id": pre_autorizada.pk, "titulo": pre_autorizada.titulo, "status": "pre_autorizada",
                "saldo_liberado": "300.00",
            },
        ],
        "saldo_por_rubrica": sorted(
            [
                {"rubrica_id": rubrica_diarias.pk, "rubrica_nome": "Diárias", "valor": "200.00"},
                {"rubrica_id": outra.pk, "rubrica_nome": "Material", "valor": "300.00"},
            ],
            key=lambda item: item["rubrica_id"],
        ),
        "saldo_liberado": "500.00",
    }
    submetida.refresh_from_db()
    assert submetida.status == "submetida"
    assert User.objects.get(pk=solicitante_rn.pk).ativo is True


def test_impacto_bate_com_o_que_a_desativacao_libera(
    auth_client_super_admin, nova_demanda, solicitante_rn, limite_individual_rn,
):
    nova_demanda("submetida", valor=200)
    nova_demanda("devolvida", valor=300)
    nova_demanda("autorizada", valor=400)
    limite_individual_rn.refresh_from_db()
    antes = limite_individual_rn.valor_comprometido

    impacto = auth_client_super_admin.get(f"/api/v1/core/usuarios/{solicitante_rn.pk}/impacto-desativacao/").json()
    auth_client_super_admin.delete(f"/api/v1/users/{solicitante_rn.pk}/")

    limite_individual_rn.refresh_from_db()
    assert antes - limite_individual_rn.valor_comprometido == Decimal(impacto["saldo_liberado"])
    assert set(Demand.objects.filter(status="cancelada").values_list("pk", flat=True)) == {
        item["id"] for item in impacto["demandas"]
    }


def test_impacto_de_usuario_sem_demandas_vem_vazio(auth_client_super_admin, solicitante_rn):
    resposta = auth_client_super_admin.get(f"/api/v1/core/usuarios/{solicitante_rn.pk}/impacto-desativacao/")

    assert resposta.status_code == 200
    assert resposta.json() == {"demandas": [], "saldo_por_rubrica": [], "saldo_liberado": "0.00"}


def test_impacto_e_so_do_super_admin(auth_client_ugp, solicitante_rn):
    resposta = auth_client_ugp.get(f"/api/v1/core/usuarios/{solicitante_rn.pk}/impacto-desativacao/")

    assert resposta.status_code == 403
