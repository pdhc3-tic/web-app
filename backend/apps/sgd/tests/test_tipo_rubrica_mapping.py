import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgd.exceptions import ErroDeDominio
from apps.sgd.models import DemandTypeRubricaMapping
from apps.sgd.services import demand as demand_service
from apps.sgd.tests.factories import DemandTypeRubricaMappingFactory
from apps.sgp.tests.factories import BudgetRubricaFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/config/tipo-rubrica/"

CAMPOS_GRAFICO = {
    "tipo_material": "banner", "quantidade": 1,
    "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
}


@pytest.fixture
def limpar_mapeamentos():
    """A migration 0010 semeia o mapeamento padrão; os testes partem de tabela vazia."""
    DemandTypeRubricaMapping.objects.all().delete()


# ---------- CRUD (Super Admin) ----------

def test_criar_editar_e_desativar_mapeamento(auth_client_super_admin, limpar_mapeamentos):
    rubrica = BudgetRubricaFactory(slug="rubrica-a")
    outra = BudgetRubricaFactory(slug="rubrica-b")

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")
    assert resp.status_code == 201
    assert resp.data["ativo"] is True
    assert resp.data["criado_em"] and resp.data["atualizado_em"]
    pk = resp.data["id"]
    assert AuditLog.objects.filter(acao="tipo_rubrica.criado", entidade_id=str(pk)).exists()

    resp = auth_client_super_admin.patch(f"{URL}{pk}/", {"rubrica": outra.pk}, format="json")
    assert resp.status_code == 200
    assert DemandTypeRubricaMapping.objects.get(pk=pk).rubrica_id == outra.pk

    resp = auth_client_super_admin.patch(f"{URL}{pk}/", {"ativo": False}, format="json")
    assert resp.status_code == 200
    assert DemandTypeRubricaMapping.objects.get(pk=pk).ativo is False

    resp = auth_client_super_admin.get(URL, {"tipo": "diaria", "ativo": "false"})
    assert resp.status_code == 200
    assert [m["id"] for m in resp.data] == [pk]

    resp = auth_client_super_admin.delete(f"{URL}{pk}/")
    assert resp.status_code == 204
    assert not DemandTypeRubricaMapping.objects.filter(pk=pk).exists()


def test_segundo_mapeamento_ativo_para_o_mesmo_tipo_retorna_400(auth_client_super_admin, limpar_mapeamentos):
    DemandTypeRubricaMappingFactory(tipo="diaria", ativo=True)
    rubrica = BudgetRubricaFactory(slug="rubrica-c")

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "tipo" in resp.data
    assert DemandTypeRubricaMapping.objects.filter(tipo="diaria").count() == 1


def test_mapeamento_inativo_nao_conflita_e_reativar_com_outro_ativo_retorna_400(
    auth_client_super_admin, limpar_mapeamentos,
):
    DemandTypeRubricaMappingFactory(tipo="diaria", ativo=True)
    rubrica = BudgetRubricaFactory(slug="rubrica-d")

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk, "ativo": False}, format="json")
    assert resp.status_code == 201

    resp = auth_client_super_admin.patch(f"{URL}{resp.data['id']}/", {"ativo": True}, format="json")
    assert resp.status_code == 400


def test_rubrica_inativa_retorna_400(auth_client_super_admin, limpar_mapeamentos):
    rubrica = BudgetRubricaFactory(slug="rubrica-inativa", ativo=False)

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "rubrica" in resp.data


# ---------- Permissão ----------

@pytest.mark.parametrize("cliente", ["auth_client_ugp", "auth_client_solicitante"])
def test_nao_super_admin_recebe_403_em_todas_as_operacoes(cliente, request, limpar_mapeamentos):
    client = request.getfixturevalue(cliente)
    mapeamento = DemandTypeRubricaMappingFactory(tipo="grafico")
    rubrica = BudgetRubricaFactory(slug="rubrica-e")

    assert client.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json").status_code == 403
    assert client.patch(f"{URL}{mapeamento.pk}/", {"ativo": False}, format="json").status_code == 403
    assert client.delete(f"{URL}{mapeamento.pk}/").status_code == 403
    assert client.get(URL).status_code == 403
    mapeamento.refresh_from_db()
    assert mapeamento.ativo is True


# ---------- Atribuição automática de rubrica ----------

def test_criacao_de_solicitacao_consulta_a_tabela_de_mapeamento(demand_rascunho_rn, limpar_mapeamentos):
    rubrica = BudgetRubricaFactory(slug="rubrica-grafico-config")
    DemandTypeRubricaMappingFactory(tipo="grafico", rubrica=rubrica)

    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    assert solicitacao.rubrica_id == rubrica.pk


def test_tipo_sem_mapeamento_ativo_retorna_validacao(demand_rascunho_rn, limpar_mapeamentos):
    DemandTypeRubricaMappingFactory(tipo="grafico", ativo=False)

    with pytest.raises(ErroDeDominio):
        demand_service.adicionar_solicitacao(
            demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
        )


def test_alterar_mapeamento_nao_muda_rubrica_de_solicitacoes_existentes(
    demand_rascunho_rn, auth_client_super_admin, limpar_mapeamentos,
):
    antiga = BudgetRubricaFactory(slug="rubrica-antiga")
    nova = BudgetRubricaFactory(slug="rubrica-nova")
    mapeamento = DemandTypeRubricaMappingFactory(tipo="grafico", rubrica=antiga)
    existente = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    resp = auth_client_super_admin.patch(f"{URL}{mapeamento.pk}/", {"rubrica": nova.pk}, format="json")
    assert resp.status_code == 200
    nova_solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    existente.refresh_from_db()
    assert existente.rubrica_id == antiga.pk
    assert nova_solicitacao.rubrica_id == nova.pk


def test_editar_solicitacao_existente_sem_trocar_tipo_mantem_a_rubrica(demand_rascunho_rn, limpar_mapeamentos):
    antiga = BudgetRubricaFactory(slug="rubrica-antiga-2")
    mapeamento = DemandTypeRubricaMappingFactory(tipo="grafico", rubrica=antiga)
    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )
    mapeamento.rubrica = BudgetRubricaFactory(slug="rubrica-nova-2")
    mapeamento.save()

    atualizada = demand_service.atualizar_solicitacao(
        solicitacao, usuario=demand_rascunho_rn.solicitante, campos_json={**CAMPOS_GRAFICO, "quantidade": 3},
    )

    assert atualizada.rubrica_id == antiga.pk
