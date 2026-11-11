"""Validação dos campos de uma solicitação: o `schema_campos` do catálogo e, para as
regras que um JSON Schema não expressa, uma estratégia registrada."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry

from apps.sgd.exceptions import RegraDeNegocio

logger = logging.getLogger(__name__)


@dataclass
class CamposValidados:
    campos_json: dict
    beneficiario_cpf: str | None
    valor_estimado_auto: Decimal | None


@dataclass(frozen=True)
class Validador:
    preparar: Callable[[dict, object], CamposValidados]
    # Regra que só faz sentido na submissão, como conferir os documentos da demanda.
    ao_submeter: Callable[[object], None] | None = None
    # Chave de `campos_json` que recebe o CPF, gravado criptografado em coluna própria.
    chave_cpf: str | None = None
    # Na edição, recebe os `campos_json` gravados e devolve o resultado com os valores
    # calculados preservados; `None` pede o recálculo por `preparar`.
    congelar: Callable[[dict, object, dict], CamposValidados | None] | None = None


_VALIDADORES: dict[str, Validador] = {}


def registrar_validador(nome: str, *, ao_submeter=None, chave_cpf: str | None = None, congelar=None):
    def registrar(funcao):
        _VALIDADORES[nome] = Validador(
            preparar=funcao, ao_submeter=ao_submeter, chave_cpf=chave_cpf, congelar=congelar,
        )
        return funcao
    return registrar


def obter_validador(nome: str) -> Validador | None:
    return _VALIDADORES.get(nome)


def validadores_registrados() -> list[str]:
    return sorted(_VALIDADORES)


def _mensagem_do_schema(schema) -> str | None:
    mensagem = schema.get("mensagem") if isinstance(schema, dict) else None
    return mensagem if isinstance(mensagem, str) else None


def _mensagem(erro) -> str:
    if (mensagem := _mensagem_do_schema(erro.schema)) is not None:
        return mensagem
    if erro.validator == "enum":
        return f"Valor inválido. Esperado um de: {sorted(erro.validator_value, key=str)}."
    return "Valor inválido."


def validar_por_schema(schema: dict, campos: dict) -> None:
    """Vazio conta como ausente, e as mensagens seguem o contrato de erro do SGD.
    O texto de uma regra pode vir em `mensagem`, na própria subseção do schema."""
    preenchidos = {campo: valor for campo, valor in campos.items() if valor not in (None, "")}
    faltando = [campo for campo in schema.get("required", []) if campo not in preenchidos]
    if faltando:
        raise RegraDeNegocio(f"Campos obrigatórios ausentes: {', '.join(faltando)}.", campo="campos_json")

    # Sem `registry`, o jsonschema busca `$ref` remoto com urlopen, sem timeout e com a demanda travada.
    validador = Draft202012Validator(schema, registry=Registry(), format_checker=FormatChecker())
    try:
        erro = next(validador.iter_errors(preenchidos), None)
        if erro is None:
            # Valores opcionais enviados também precisam obedecer ao schema antes de persistir.
            erro = next(validador.iter_errors(campos), None)
    # `check_schema` não segue `$ref`, e as exceções de um alvo inválido ou circular variam
    # com a palavra-chave: qualquer falha ao aplicar o schema é defeito dele, não dos campos.
    except Exception as exc:
        logger.warning("Falha ao aplicar o schema de um tipo de solicitação.", exc_info=True)
        raise RegraDeNegocio("O schema deste tipo é inválido. Contate o Super Admin.", campo="tipo") from exc
    if erro is None:
        return
    if erro.validator == "required":
        campo = next(nome for nome in erro.validator_value if nome not in erro.instance)
        caminho = [*erro.absolute_path, campo]
        raise RegraDeNegocio(
            _mensagem_do_schema(erro.schema) or "Obrigatório.", campo=".".join(map(str, caminho)),
        )
    raise RegraDeNegocio(_mensagem(erro), campo=str(erro.absolute_path[0]) if erro.absolute_path else "campos_json")
