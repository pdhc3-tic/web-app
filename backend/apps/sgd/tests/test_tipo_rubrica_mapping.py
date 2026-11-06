"""Alias `/sgd/config/tipo-rubrica/`: o contrato da tela de mapeamento, sobre o catálogo de tipos."""
import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgd.exceptions import ErroDeDominio
from apps.sgd.models import TipoSolicitacao
from apps.sgd.services import demand as demand_service
from apps.sgd.tests.factories import mapear_tipo
from apps.sgp.tests.factories import BudgetRubricaFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgd/config/tipo-rubrica/"

CAMPOS_GRAFICO = {
    "tipo_material": "banner", "quantidade": 1,
    "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
}


def _tipo(slug):
    return TipoSolicitacao.objects.get(slug=slug)


# ---------- Contrato (Super Admin) ----------

def test_lista_uma_linha_por_tipo_com_o_contrato_da_tela(auth_client_super_admin):
    rubrica = BudgetRubricaFactory(slug="rubrica-a", nome="Rubrica A")
    tipo = mapear_tipo("diaria", rubrica)

    resp = auth_client_super_admin.get(URL, {"tipo": "diaria"})

    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["id"] == tipo.pk
    assert resp.data[0]["tipo"] == "diaria"
    assert (resp.data[0]["rubrica"], resp.data[0]["rubrica_nome"]) == (rubrica.pk, "Rubrica A")
    assert resp.data[0]["ativo"] is True
    assert resp.data[0]["criado_em"] and resp.data[0]["atualizado_em"]


def test_patch_troca_a_rubrica_e_desativa_o_tipo(auth_client_super_admin):
    tipo = _tipo("diaria")
    outra = BudgetRubricaFactory(slug="rubrica-b")

    resp = auth_client_super_admin.patch(f"{URL}{tipo.pk}/", {"rubrica": outra.pk}, format="json")
    assert resp.status_code == 200
    assert _tipo("diaria").rubrica_id == outra.pk
    assert AuditLog.objects.filter(acao="tipo_rubrica.alterado", entidade_id=str(tipo.pk)).exists()

    resp = auth_client_super_admin.patch(f"{URL}{tipo.pk}/", {"ativo": False}, format="json")
    assert resp.status_code == 200
    assert _tipo("diaria").ativo is False

    resp = auth_client_super_admin.get(URL, {"tipo": "diaria", "ativo": "false"})
    assert [m["id"] for m in resp.data] == [tipo.pk]


def test_post_em_tipo_ativo_responde_o_erro_de_duplicado(auth_client_super_admin):
    rubrica = BudgetRubricaFactory(slug="rubrica-c")

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "tipo" in resp.data
    assert _tipo("diaria").rubrica_id != rubrica.pk


def test_post_em_tipo_inativo_reativa_com_a_rubrica_enviada(auth_client_super_admin):
    TipoSolicitacao.objects.filter(slug="diaria").update(ativo=False)
    rubrica = BudgetRubricaFactory(slug="rubrica-d")

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 201
    assert resp.data["id"] == _tipo("diaria").pk
    assert resp.data["ativo"] is True
    assert _tipo("diaria").rubrica_id == rubrica.pk
    assert AuditLog.objects.filter(acao="tipo_rubrica.criado", entidade_id=str(resp.data["id"])).exists()


def test_post_de_tipo_que_nao_existe_no_catalogo_retorna_400(auth_client_super_admin):
    rubrica = BudgetRubricaFactory(slug="rubrica-e")

    resp = auth_client_super_admin.post(URL, {"tipo": "inexistente", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "tipo" in resp.data


def test_delete_desativa_o_tipo_sem_apagar(auth_client_super_admin):
    tipo = _tipo("diaria")

    resp = auth_client_super_admin.delete(f"{URL}{tipo.pk}/")

    assert resp.status_code == 204
    assert _tipo("diaria").ativo is False


def test_rubrica_inativa_retorna_400(auth_client_super_admin):
    TipoSolicitacao.objects.filter(slug="diaria").update(ativo=False)
    rubrica = BudgetRubricaFactory(slug="rubrica-inativa", ativo=False)

    resp = auth_client_super_admin.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json")

    assert resp.status_code == 400
    assert "rubrica" in resp.data


# ---------- Permissão ----------

@pytest.mark.parametrize("cliente", ["auth_client_ugp", "auth_client_solicitante"])
def test_nao_super_admin_recebe_403_em_todas_as_operacoes(cliente, request):
    client = request.getfixturevalue(cliente)
    tipo = _tipo("grafico")
    rubrica = BudgetRubricaFactory(slug="rubrica-f")

    assert client.post(URL, {"tipo": "diaria", "rubrica": rubrica.pk}, format="json").status_code == 403
    assert client.patch(f"{URL}{tipo.pk}/", {"ativo": False}, format="json").status_code == 403
    assert client.delete(f"{URL}{tipo.pk}/").status_code == 403
    assert client.get(URL).status_code == 403
    assert _tipo("grafico").ativo is True


# ---------- Atribuição automática de rubrica ----------

def test_criacao_de_solicitacao_consulta_o_catalogo(demand_rascunho_rn):
    rubrica = BudgetRubricaFactory(slug="rubrica-grafico-config")
    mapear_tipo("grafico", rubrica)

    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    assert solicitacao.rubrica_id == rubrica.pk


def test_tipo_inativo_nao_aceita_solicitacao_nova(demand_rascunho_rn):
    TipoSolicitacao.objects.filter(slug="grafico").update(ativo=False)

    with pytest.raises(ErroDeDominio):
        demand_service.adicionar_solicitacao(
            demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
        )


def test_alterar_a_rubrica_nao_muda_solicitacoes_existentes(demand_rascunho_rn, auth_client_super_admin):
    antiga = BudgetRubricaFactory(slug="rubrica-antiga")
    nova = BudgetRubricaFactory(slug="rubrica-nova")
    tipo = mapear_tipo("grafico", antiga)
    existente = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    resp = auth_client_super_admin.patch(f"{URL}{tipo.pk}/", {"rubrica": nova.pk}, format="json")
    assert resp.status_code == 200
    nova_solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )

    existente.refresh_from_db()
    assert existente.rubrica_id == antiga.pk
    assert nova_solicitacao.rubrica_id == nova.pk


def test_editar_solicitacao_existente_sem_trocar_tipo_mantem_a_rubrica(demand_rascunho_rn):
    antiga = BudgetRubricaFactory(slug="rubrica-antiga-2")
    mapear_tipo("grafico", antiga)
    solicitacao = demand_service.adicionar_solicitacao(
        demand_rascunho_rn, tipo="grafico", campos_json=CAMPOS_GRAFICO, valor_estimado=100,
    )
    mapear_tipo("grafico", BudgetRubricaFactory(slug="rubrica-nova-2"))

    atualizada = demand_service.atualizar_solicitacao(
        solicitacao, usuario=demand_rascunho_rn.solicitante, campos_json={**CAMPOS_GRAFICO, "quantidade": 3},
    )

    assert atualizada.rubrica_id == antiga.pk
