"""Exceções de domínio do SGD. Os serviços não conhecem HTTP: quem traduz para
a resposta é `setup.exceptions.custom_exception_handler`."""
from __future__ import annotations

from decimal import Decimal


class ErroDeDominio(Exception):
    code = "BUSINESS_RULE"
    campo_padrao: str | None = None

    def __init__(self, mensagem: str = "", *, campo: str | None = None, erros: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campo = campo if campo is not None else self.campo_padrao
        self.erros = erros

    def como_dict(self) -> dict:
        # Erro de campo mantém o formato {campo: [msg]} que o frontend já
        # associa ao campo do formulário; o `code` vai por último para não ser
        # lido como a primeira mensagem.
        if self.erros is not None:
            return {**self.erros, "code": self.code}
        if self.campo:
            return {self.campo: [self.mensagem], "code": self.code}
        return {"code": self.code, "detail": self.mensagem}


class RegraDeNegocio(ErroDeDominio):
    code = "BUSINESS_RULE"


class TransicaoInvalida(ErroDeDominio):
    code = "INVALID_TRANSITION"
    campo_padrao = "status"


class JustificativaObrigatoria(ErroDeDominio):
    code = "JUSTIFICATION_REQUIRED"
    campo_padrao = "justificativa"


TRAVA_INDIVIDUAL = "individual"
TRAVA_TERRITORIAL = "territorial"

ACAO_SUGERIDA = {
    TRAVA_INDIVIDUAL: "solicitar_recurso_extra",
    TRAVA_TERRITORIAL: "acionar_articulador",
}


def _valor(valor: Decimal) -> str:
    return f"{Decimal(valor):.2f}"


class SaldoInsuficiente(ErroDeDominio):
    """Bloqueio por uma das duas travas. Numa submissão com várias
    solicitações, o primeiro bloqueio vai no topo e todos aparecem em
    `solicitacoes_bloqueadas`, cada um no mesmo formato."""

    code = "INSUFFICIENT_BALANCE"

    def __init__(self, *, trava: str, rubrica: str, disponivel: Decimal, solicitado: Decimal,
                 detail: str, acao_sugerida: str | None = None, solicitacao_id: int | None = None,
                 valor_faltante: Decimal | None = None):
        super().__init__(detail)
        self.trava = trava
        self.rubrica = rubrica
        self.disponivel = disponivel
        self.solicitado = solicitado
        # Só na trava individual da submissão: o que falta na rubrica inteira, que
        # `disponivel` e `solicitado` (da solicitação barrada) não dão para calcular.
        self.valor_faltante = valor_faltante
        self.acao_sugerida = acao_sugerida or ACAO_SUGERIDA[trava]
        self.solicitacao_id = solicitacao_id
        self.bloqueios: dict[int, SaldoInsuficiente] = {}

    @classmethod
    def para_submissao(cls, bloqueios: dict[int, SaldoInsuficiente]) -> SaldoInsuficiente:
        solicitacao_id, primeiro = next(iter(bloqueios.items()))
        erro = cls(
            trava=primeiro.trava, rubrica=primeiro.rubrica, disponivel=primeiro.disponivel,
            solicitado=primeiro.solicitado, acao_sugerida=primeiro.acao_sugerida,
            detail=primeiro.mensagem, solicitacao_id=solicitacao_id, valor_faltante=primeiro.valor_faltante,
        )
        erro.bloqueios = bloqueios
        return erro

    def _corpo(self) -> dict:
        return {
            "code": self.code,
            "trava": self.trava,
            "rubrica": self.rubrica,
            "disponivel": _valor(self.disponivel),
            "solicitado": _valor(self.solicitado),
            "acao_sugerida": self.acao_sugerida,
            "valor_faltante": _valor(self.valor_faltante) if self.valor_faltante is not None else None,
            "detail": self.mensagem,
        }

    def como_dict(self) -> dict:
        corpo = self._corpo()
        if self.solicitacao_id is not None:
            corpo["solicitacao_id"] = self.solicitacao_id
            bloqueios = self.bloqueios or {self.solicitacao_id: self}
            corpo["solicitacoes_bloqueadas"] = {str(pk): b._corpo() for pk, b in bloqueios.items()}
        return corpo
