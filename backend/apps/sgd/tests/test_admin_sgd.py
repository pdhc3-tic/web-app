"""O Django Admin não desfaz o saldo gravado por outra operação nem passa por
cima das regras que a API aplica ao limite individual, à demanda e à solicitação."""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.admin.sites import site
from django.core.cache import cache
from django.db import connection
from django.forms.models import model_to_dict
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import UserFactory
from apps.sgd.models import Demand, DemandRequest
from apps.sgd.services import balance as balance_service
from apps.sgd.services.reconciliacao import divergencias_dos_limites
from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.sgp.budget import limites
from apps.sgp.models import SpendingLimit
from apps.sgp.tests.factories import BudgetPoolFactory

pytestmark = pytest.mark.django_db


def _request_de_super_admin(method="post"):
    request = getattr(RequestFactory(), method)("/")
    request.user = UserFactory(is_superuser=True)
    return request


def _formulario_de_edicao(carregado, **alteracoes):
    """Formulário de edição preenchido com os valores de `carregado`, como o
    Admin o mostraria, mais `alteracoes`."""
    model_admin = site._registry[type(carregado)]
    request = _request_de_super_admin()
    formulario = model_admin.get_form(request, carregado, change=True)
    dados = {
        campo: json.dumps(valor) if isinstance(valor, (dict, list)) else valor
        for campo, valor in model_to_dict(carregado, fields=formulario.base_fields).items()
        if valor is not None
    }
    return formulario(data={**dados, **alteracoes}, instance=carregado)


def _salvar_pelo_admin(carregado, **alteracoes):
    form = _formulario_de_edicao(carregado, **alteracoes)
    assert form.is_valid(), form.errors
    model_admin = site._registry[type(carregado)]
    model_admin.save_model(_request_de_super_admin(), form.save(commit=False), form, change=True)


@pytest.mark.parametrize("modelo", [Demand, DemandRequest])
def test_admin_so_consulta_demanda_e_solicitacao(modelo, demand_request_rn):
    model_admin = site._registry[modelo]
    request = _request_de_super_admin("get")
    obj = demand_request_rn if modelo is DemandRequest else demand_request_rn.demanda

    assert model_admin.has_view_permission(request, obj)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, obj)
    assert not model_admin.has_delete_permission(request, obj)


def test_solicitacao_salva_pelo_admin_mantem_a_reserva_feita_depois_da_leitura(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    carregada_pelo_admin = DemandRequest.objects.get(pk=demand_request_rn.pk)
    balance_service.reservar_duas_travas(
        demand_request=DemandRequest.objects.get(pk=demand_request_rn.pk), usuario=solicitante_rn,
    )

    _salvar_pelo_admin(carregada_pelo_admin, ordem=3)

    demand_request_rn.refresh_from_db()
    limite_individual_rn.refresh_from_db()
    assert demand_request_rn.valor_reservado == Decimal("1000")
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    assert divergencias_dos_limites() == []


def test_limite_salvo_pelo_admin_mantem_o_comprometido_gravado_depois_da_leitura(
    demand_request_rn, solicitante_rn, allocation_territorial_rn, limite_individual_rn,
):
    carregado_pelo_admin = SpendingLimit.objects.get(pk=limite_individual_rn.pk)
    balance_service.reservar_duas_travas(demand_request=demand_request_rn, usuario=solicitante_rn)

    _salvar_pelo_admin(carregado_pelo_admin, valor_limite="6000")

    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("6000")
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    assert divergencias_dos_limites() == []


def test_admin_nao_move_o_limite_para_outro_solicitante_ou_rubrica(limite_individual_rn):
    readonly = site._registry[SpendingLimit].get_readonly_fields(
        _request_de_super_admin("get"), limite_individual_rn,
    )
    na_criacao = site._registry[SpendingLimit].get_readonly_fields(_request_de_super_admin("get"))

    assert {"user", "rubrica"} <= set(readonly)
    assert not {"user", "rubrica"} & set(na_criacao)


def test_admin_aceita_reduzir_abaixo_do_comprometido(limite_individual_rn):
    # O rebaixamento preserva o comprometido; o novo teto vale para as próximas reservas.
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(
        valor_comprometido=Decimal("3000"), valor_executado=Decimal("1000"),
    )
    limite_individual_rn.refresh_from_db()

    assert _formulario_de_edicao(limite_individual_rn, valor_limite="3999.99").is_valid()


def test_admin_recusa_limite_negativo(limite_individual_rn):
    form = _formulario_de_edicao(limite_individual_rn, valor_limite="-1")

    assert form.errors["valor_limite"] == ["Não pode ser negativo."]


def test_admin_trava_o_limite_so_no_post_da_edicao(limite_individual_rn):
    model_admin = site._registry[SpendingLimit]
    post, get = _request_de_super_admin("post"), _request_de_super_admin("get")

    with CaptureQueriesContext(connection) as no_post:
        model_admin.get_object(post, str(limite_individual_rn.pk))
    with CaptureQueriesContext(connection) as no_get:
        model_admin.get_object(get, str(limite_individual_rn.pk))

    assert any("FOR UPDATE" in q["sql"] for q in no_post.captured_queries)
    assert not any("FOR UPDATE" in q["sql"] for q in no_get.captured_queries)


@pytest.mark.parametrize("campo", ["valor_comprometido", "valor_executado"])
def test_admin_nao_exclui_limite_com_saldo(campo, limite_individual_rn):
    model_admin = site._registry[SpendingLimit]
    request = _request_de_super_admin("post")
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(**{campo: Decimal("1")})

    travado = model_admin.get_object(request, str(limite_individual_rn.pk))

    assert not model_admin.has_delete_permission(request, travado)


def test_admin_exclui_limite_sem_saldo_e_nao_oferece_exclusao_em_lote(limite_individual_rn):
    model_admin = site._registry[SpendingLimit]
    request = _request_de_super_admin("get")

    assert model_admin.has_delete_permission(request, limite_individual_rn)
    assert "delete_selected" not in model_admin.get_actions(request)


@pytest.fixture
def super_admin():
    return UserFactory(is_superuser=True)


@pytest.fixture
def client_super_admin(client, super_admin):
    client.force_login(super_admin)
    return client


def _url_do_limite(limite, acao="change"):
    return f"/admin/sgp/spendinglimit/{limite.pk}/{acao}/"


def test_post_do_admin_altera_so_o_valor_limite(client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("1000"))
    outro_solicitante = UserFactory()

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
        "valor_limite": "6000", "justificativa": "Ajuste no Admin.", "user": outro_solicitante.pk, "_save": "Salvar",
    })

    assert resposta.status_code == 302
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("6000")
    assert limite_individual_rn.valor_comprometido == Decimal("1000")
    assert limite_individual_rn.user_id != outro_solicitante.pk


def test_post_do_admin_reduz_abaixo_do_comprometido_sem_mexer_no_saldo(client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("3000"))

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
        "valor_limite": "2000", "justificativa": "Revisão.", "_save": "Salvar",
    })

    assert resposta.status_code == 302
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("2000")
    assert limite_individual_rn.valor_comprometido == Decimal("3000")


def test_admin_recusa_aumento_acima_do_pool_com_sobrealocacao_desligada(
    client_super_admin, limite_individual_rn, allocation_territorial_rn, territory_rn,
):
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(territorio=territory_rn)
    SystemConfig.objects.update_or_create(
        chave="budget_overallocation_allowed", defaults={"valor": "False", "tipo": TipoConfiguracao.BOOLEAN},
    )
    try:
        resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
            "valor_limite": "99999", "justificativa": "Aumento.", "territorio": territory_rn.pk, "_save": "Salvar",
        })
    finally:
        cache.delete("system_config:budget_overallocation_allowed")

    assert resposta.status_code == 200
    assert "passa do pool" in resposta.content.decode()
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("5000")


def test_admin_nao_altera_padrao_por_perfil(client_super_admin, solicitante_rn, rubrica_diarias):
    from datetime import date

    from apps.sgp.budget.limites import FIM_EM_ABERTO

    padrao = SpendingLimit.objects.create(
        escopo=SpendingLimit.Escopo.PERFIL, perfil=solicitante_rn.profiles.get().perfil, rubrica=rubrica_diarias,
        valor_limite=Decimal("1000"), periodo_inicio=date(2026, 1, 1), periodo_fim=FIM_EM_ABERTO,
    )

    resposta = client_super_admin.post(_url_do_limite(padrao), {"valor_limite": "9000", "_save": "Salvar"})

    assert resposta.status_code == 403
    padrao.refresh_from_db()
    assert padrao.valor_limite == Decimal("1000")


def test_admin_do_pool_e_so_consulta(client_super_admin, allocation_territorial_rn):
    url = f"/admin/sgp/budgetpool/{allocation_territorial_rn.pk}/change/"
    valor = allocation_territorial_rn.valor_alocado

    leitura = client_super_admin.get(url)
    edicao = client_super_admin.post(url, {"valor_alocado": "1", "_save": "Salvar"})
    exclusao = client_super_admin.post(f"/admin/sgp/budgetpool/{allocation_territorial_rn.pk}/delete/", {"post": "yes"})
    criacao = client_super_admin.get("/admin/sgp/budgetpool/add/")

    assert leitura.status_code == 200
    assert (edicao.status_code, exclusao.status_code, criacao.status_code) == (403, 403, 403)
    allocation_territorial_rn.refresh_from_db()
    assert allocation_territorial_rn.valor_alocado == valor


def test_post_do_admin_nao_exclui_limite_com_saldo(client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(valor_comprometido=Decimal("1000"))

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn, "delete"), {"post": "yes"})

    assert resposta.status_code == 403
    assert SpendingLimit.objects.filter(pk=limite_individual_rn.pk).exists()


def test_admin_mostra_demanda_e_solicitacao_para_consulta(client_super_admin, demand_request_rn):
    ordem_antes = demand_request_rn.ordem
    resposta_demanda = client_super_admin.get(f"/admin/sgd/demand/{demand_request_rn.demanda_id}/change/")
    resposta_solicitacao = client_super_admin.get(f"/admin/sgd/demandrequest/{demand_request_rn.pk}/change/")
    tentativa_de_edicao = client_super_admin.post(
        f"/admin/sgd/demandrequest/{demand_request_rn.pk}/change/", {"ordem": ordem_antes + 1, "_save": "Salvar"},
    )

    assert resposta_demanda.status_code == 200
    assert resposta_solicitacao.status_code == 200
    assert tentativa_de_edicao.status_code == 403
    demand_request_rn.refresh_from_db()
    assert demand_request_rn.ordem == ordem_antes


def test_criacao_e_alteracao_pelo_admin_ficam_na_auditoria(
    client_super_admin, super_admin, solicitante_rn, rubrica_diarias,
):
    criado = client_super_admin.post("/admin/sgp/spendinglimit/add/", {
        "escopo": "individual", "user": solicitante_rn.pk, "rubrica": rubrica_diarias.pk, "valor_limite": "1000",
        "justificativa": "Criado no Admin.", "periodo_inicio": "2026-10-01", "periodo_fim": "2026-12-31",
        "valor_comprometido": "0", "valor_executado": "0", "_save": "Salvar",
    })
    assert criado.status_code == 302
    limite = SpendingLimit.objects.get(user=solicitante_rn, rubrica=rubrica_diarias)

    for _ in range(2):
        resposta = client_super_admin.post(_url_do_limite(limite), {"valor_limite": "1500", "justificativa": "Ajuste no Admin.", "_save": "Salvar"})
        assert resposta.status_code == 302

    limite.refresh_from_db()
    assert limite.criado_por == super_admin
    eventos = AuditLog.objects.filter(entidade="SpendingLimit", entidade_id=str(limite.pk)).order_by("id")
    assert [e.acao for e in eventos] == ["limite_individual.criado", "limite_individual.alterado"]
    assert eventos.last().user == super_admin
    assert eventos.last().valores_anteriores == {"valor_limite": "1000.00"}


def _corpo_do_novo_limite(user, rubrica, valor):
    inicio, fim = limites.periodo_de(limites.hoje())
    return {
        "escopo": "individual", "user": user, "rubrica": rubrica.pk, "valor_limite": valor,
        "justificativa": "Criado no Admin.", "periodo_inicio": inicio.isoformat(), "periodo_fim": fim.isoformat(),
        "_save": "Salvar",
    }


def test_admin_sem_usuario_devolve_erro_no_formulario(client_super_admin, rubrica_diarias):
    resposta = client_super_admin.post(
        "/admin/sgp/spendinglimit/add/", _corpo_do_novo_limite("", rubrica_diarias, "1000"),
    )

    assert resposta.status_code == 200
    assert "user" in resposta.context["adminform"].form.errors
    assert not SpendingLimit.objects.exists()


def test_admin_nao_soma_o_padrao_ao_valor_da_linha_nova(client_super_admin, solicitante_rn, rubrica_diarias, territory_rn):
    SpendingLimit.objects.create(
        escopo=SpendingLimit.Escopo.PERFIL, perfil=solicitante_rn.profiles.first().perfil, rubrica=rubrica_diarias,
        valor_limite=Decimal("1000"), periodo_inicio=date(2026, 1, 1), periodo_fim=limites.FIM_EM_ABERTO,
    )
    BudgetPoolFactory(rubrica=rubrica_diarias, territorio=territory_rn, valor_alocado=Decimal("1500"))
    SystemConfig.objects.update_or_create(
        chave="budget_overallocation_allowed", defaults={"valor": "False", "tipo": TipoConfiguracao.BOOLEAN},
    )
    cache.delete("system_config:budget_overallocation_allowed")

    try:
        resposta = client_super_admin.post(
            "/admin/sgp/spendinglimit/add/", _corpo_do_novo_limite(solicitante_rn.pk, rubrica_diarias, "1000"),
        )
    finally:
        cache.delete("system_config:budget_overallocation_allowed")

    assert resposta.status_code == 302
    assert SpendingLimit.objects.get(user=solicitante_rn).valor_limite == Decimal("1000")


def test_admin_exige_justificativa_ao_mudar_o_valor_da_linha_herdada(client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(herdado=True, justificativa="")

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
        "valor_limite": "9000", "justificativa": "", "_save": "Salvar",
    })

    assert resposta.status_code == 200
    assert "justificativa" in resposta.context["adminform"].form.errors
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("5000")


def test_admin_transforma_em_sobrescrita_a_linha_herdada_com_valor_novo(client_super_admin, limite_individual_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(herdado=True, justificativa="")

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
        "valor_limite": "9000", "justificativa": "Aumento pontual.", "_save": "Salvar",
    })

    assert resposta.status_code == 302
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.valor_limite == Decimal("9000")
    assert limite_individual_rn.herdado is False


def test_admin_nao_edita_o_territorio_nem_o_herdado(client_super_admin, limite_individual_rn, territory_rn):
    SpendingLimit.objects.filter(pk=limite_individual_rn.pk).update(territorio=territory_rn)

    resposta = client_super_admin.post(_url_do_limite(limite_individual_rn), {
        "valor_limite": "5000", "justificativa": "Definido no teste.", "territorio": "", "herdado": "on", "_save": "Salvar",
    })

    assert resposta.status_code == 302
    limite_individual_rn.refresh_from_db()
    assert limite_individual_rn.territorio_id == territory_rn.pk
    assert limite_individual_rn.herdado is False
