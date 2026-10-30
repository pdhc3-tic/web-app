from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.utils import formatar_brl
from apps.sgd.exceptions import JustificativaObrigatoria, RegraDeNegocio, SaldoInsuficiente, TransicaoInvalida
from setup.exceptions import custom_exception_handler

DETAIL_INDIVIDUAL = "Limite individual insuficiente: R$ 350,00 disponível, R$ 900,00 solicitado."


def _responder(exc):
    return custom_exception_handler(exc, {})


def _saldo_insuficiente(**overrides):
    dados = {
        "trava": "individual", "rubrica": "diarias", "disponivel": Decimal("350"),
        "solicitado": Decimal("900"), "detail": DETAIL_INDIVIDUAL,
    }
    dados.update(overrides)
    return SaldoInsuficiente(**dados)


def test_saldo_insuficiente_responde_400_no_contrato_insufficient_balance():
    resposta = _responder(_saldo_insuficiente())

    assert resposta.status_code == 400
    assert resposta.data == {
        "code": "INSUFFICIENT_BALANCE",
        "trava": "individual",
        "rubrica": "diarias",
        "disponivel": "350.00",
        "solicitado": "900.00",
        "acao_sugerida": "solicitar_recurso_extra",
        "valor_faltante": None,
        "detail": DETAIL_INDIVIDUAL,
    }


def test_saldo_insuficiente_territorial_sugere_acionar_o_articulador():
    resposta = _responder(_saldo_insuficiente(trava="territorial", detail="Território esgotado."))

    assert resposta.data["acao_sugerida"] == "acionar_articulador"


def test_saldo_insuficiente_da_submissao_traz_cada_bloqueio_no_mesmo_formato():
    individual = _saldo_insuficiente(solicitacao_id=10)
    territorial = _saldo_insuficiente(
        trava="territorial", disponivel=Decimal("0"), solicitado=Decimal("50"), detail="Território esgotado.",
        solicitacao_id=11,
    )

    resposta = _responder(SaldoInsuficiente.para_submissao({10: individual, 11: territorial}))

    corpo = resposta.data
    assert resposta.status_code == 400
    assert corpo["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["trava"] == "individual"
    assert corpo["detail"] == DETAIL_INDIVIDUAL
    assert corpo["solicitacao_id"] == 10
    assert set(corpo["solicitacoes_bloqueadas"]) == {"10", "11"}
    campos_do_topo = set(corpo) - {"solicitacao_id", "solicitacoes_bloqueadas"}
    for bloqueio in corpo["solicitacoes_bloqueadas"].values():
        assert set(bloqueio) == campos_do_topo
        assert bloqueio["code"] == "INSUFFICIENT_BALANCE"
    assert corpo["solicitacoes_bloqueadas"]["11"] == {
        "code": "INSUFFICIENT_BALANCE",
        "trava": "territorial",
        "rubrica": "diarias",
        "disponivel": "0.00",
        "solicitado": "50.00",
        "acao_sugerida": "acionar_articulador",
        "valor_faltante": None,
        "detail": "Território esgotado.",
    }


def test_valor_faltante_da_trava_individual_vai_no_topo_e_no_bloqueio():
    individual = _saldo_insuficiente(solicitacao_id=10, valor_faltante=Decimal("1000"))

    corpo = _responder(SaldoInsuficiente.para_submissao({10: individual})).data

    assert corpo["valor_faltante"] == "1000.00"
    assert corpo["solicitacoes_bloqueadas"]["10"]["valor_faltante"] == "1000.00"


def test_saldo_insuficiente_de_uma_solicitacao_lista_ela_mesma_como_bloqueada():
    corpo = _responder(_saldo_insuficiente(solicitacao_id=7)).data

    assert corpo["solicitacao_id"] == 7
    assert list(corpo["solicitacoes_bloqueadas"]) == ["7"]


@pytest.mark.parametrize(
    ("exc", "esperado"),
    [
        (
            TransicaoInvalida("Transição inválida: 'rascunho' → 'autorizada'."),
            {"status": ["Transição inválida: 'rascunho' → 'autorizada'."], "code": "INVALID_TRANSITION"},
        ),
        (
            JustificativaObrigatoria("Obrigatória para recusar a demanda."),
            {"justificativa": ["Obrigatória para recusar a demanda."], "code": "JUSTIFICATION_REQUIRED"},
        ),
        (
            RegraDeNegocio("Deve ser maior que zero.", campo="valor_estimado"),
            {"valor_estimado": ["Deve ser maior que zero."], "code": "BUSINESS_RULE"},
        ),
        (
            RegraDeNegocio("Nenhuma alocação territorial encontrada para remanejar."),
            {"code": "BUSINESS_RULE", "detail": "Nenhuma alocação territorial encontrada para remanejar."},
        ),
        (
            RegraDeNegocio(erros={"status": [{"message": "Escolha inválida.", "code": "invalid_choice"}]}),
            {"status": [{"message": "Escolha inválida.", "code": "invalid_choice"}], "code": "BUSINESS_RULE"},
        ),
    ],
)
def test_erros_de_dominio_respondem_400_com_code(exc, esperado):
    resposta = _responder(exc)

    assert resposta.status_code == 400
    assert resposta.data == esperado


def test_erro_de_campo_deixa_o_code_por_ultimo():
    # O frontend usa a primeira chave como mensagem quando não há `detail`.
    corpo = _responder(RegraDeNegocio("Município não encontrado.", campo="municipio_destino_id")).data

    assert list(corpo) == ["municipio_destino_id", "code"]


def test_permission_denied_do_django_continua_403_com_a_mensagem():
    resposta = _responder(PermissionDenied("Você não pode decidir sobre a própria demanda."))

    assert resposta.status_code == 403
    assert resposta.data == {"detail": "Você não pode decidir sobre a própria demanda."}


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (Decimal("0"), "R$ 0,00"),
        (Decimal("350"), "R$ 350,00"),
        (Decimal("1234.56"), "R$ 1.234,56"),
        (Decimal("1000000"), "R$ 1.000.000,00"),
        (Decimal("0.5"), "R$ 0,50"),
        (Decimal("-350.5"), "R$ -350,50"),
    ],
)
def test_formatar_brl(valor, esperado):
    assert formatar_brl(valor) == esperado
