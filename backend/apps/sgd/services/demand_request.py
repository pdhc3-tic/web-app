from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.municipality import Municipality
from apps.core.utils import get_config
from apps.sgp.validators import validate_cpf

# Usado só se SystemConfig("sgd_mapeamento_tipo_rubrica") ainda não existir.
DEFAULT_TIPO_RUBRICA_MAP = {
    "diaria": "diarias",
    "passagem": "passagens-aereas",
    "veiculo": "locacao-veiculo",
    "grafico": "material-grafico",
    "alimentacao": "alimentacao-refeicoes",
    "equipamento": "equipamentos-capital",
}

_VINCULO_CHOICES = {"servidor_ufersa", "bolsista", "colaborador_externo"}
_MEIO_TRANSPORTE_CHOICES = {"aereo", "rodoviario", "proprio", "outro"}
_CLASSE_CHOICES = {"economica", "executiva"}
_URGENCIA_CHOICES = {"normal", "urgente", "emergencial"}
_TIPO_VEICULO_CHOICES = {"hatch", "sedan", "suv", "van", "micro_onibus", "onibus"}
_TIPO_MATERIAL_CHOICES = {
    "banner", "folder", "camiseta", "bloco", "caneta", "chapeu", "kit_evento", "outro",
}
_TIPO_REFEICAO_CHOICES = {
    "cafe_manha", "almoco", "jantar", "coffee_break", "kit_lanche", "marmitex",
}


@dataclass
class CamposValidados:
    campos_json: dict
    beneficiario_cpf: str | None
    valor_estimado_auto: Decimal | None


def rubrica_slug_para_tipo(tipo: str) -> str:
    mapeamento = get_config("sgd_mapeamento_tipo_rubrica", DEFAULT_TIPO_RUBRICA_MAP) or {}
    slug = mapeamento.get(tipo)
    if not slug:
        raise DRFValidationError(
            {"tipo": f"Nenhuma rubrica mapeada para o tipo '{tipo}'. Configure em Super Admin."}
        )
    return slug


def _obrigatorios(campos: dict, nomes: list[str]) -> None:
    faltando = [n for n in nomes if campos.get(n) in (None, "")]
    if faltando:
        raise DRFValidationError(
            {"campos_json": f"Campos obrigatórios ausentes: {', '.join(faltando)}."}
        )


def _choice(campos: dict, campo: str, valores: set[str]) -> None:
    if campos.get(campo) not in valores:
        raise DRFValidationError({campo: f"Valor inválido. Esperado um de: {sorted(valores)}."})


def _positivo(campos: dict, campo: str) -> None:
    try:
        valor = int(campos[campo])
    except (TypeError, ValueError):
        raise DRFValidationError({campo: "Deve ser um número inteiro."})
    if valor <= 0:
        raise DRFValidationError({campo: "Deve ser maior que zero."})


def _parse_date(valor) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise DRFValidationError({"data": f"Data inválida: {valor!r}."})


def _parse_decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        raise DRFValidationError({"valor": f"Valor decimal inválido: {valor!r}."})


def _validar_diaria(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "beneficiario_nome", "beneficiario_cpf", "beneficiario_cargo",
        "beneficiario_vinculo", "municipio_destino_id", "data_inicio",
        "data_fim", "meio_transporte", "justificativa",
    ])
    _choice(campos, "beneficiario_vinculo", _VINCULO_CHOICES)
    _choice(campos, "meio_transporte", _MEIO_TRANSPORTE_CHOICES)
    if not Municipality.objects.filter(pk=campos["municipio_destino_id"]).exists():
        raise DRFValidationError({"municipio_destino_id": "Município não encontrado."})

    cpf = validate_cpf(campos["beneficiario_cpf"])

    data_inicio = _parse_date(campos["data_inicio"])
    data_fim = _parse_date(campos["data_fim"])
    if data_fim < data_inicio:
        raise DRFValidationError({"data_fim": "Não pode ser anterior à data de início."})

    numero_diarias = max((data_fim - data_inicio).days, 1)
    valor_por_diaria = _parse_decimal(get_config("sgd_valor_diaria_padrao", "0"))
    if valor_por_diaria <= 0:
        raise DRFValidationError({
            "valor_por_diaria": "Valor de diária não configurado — contate o Super Admin (sgd_valor_diaria_padrao)."
        })
    valor_total = numero_diarias * valor_por_diaria

    campos_limpos = {k: v for k, v in campos.items() if k != "beneficiario_cpf"}
    campos_limpos.update({
        "numero_diarias": numero_diarias,
        "valor_por_diaria": str(valor_por_diaria),
        "valor_total": str(valor_total),
    })
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=valor_total)


def _validar_passagem(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "passageiro_nome", "passageiro_cpf", "passageiro_data_nascimento",
        "aeroporto_origem", "aeroporto_destino", "data_hora_ida", "ida_e_volta",
        "bagagem_despachada", "classe", "urgencia",
    ])
    _choice(campos, "classe", _CLASSE_CHOICES)
    _choice(campos, "urgencia", _URGENCIA_CHOICES)
    if campos["ida_e_volta"] not in (True, False):
        raise DRFValidationError({"ida_e_volta": "Deve ser um booleano."})

    if campos["ida_e_volta"] and not campos.get("data_hora_volta"):
        raise DRFValidationError(
            {"data_hora_volta": "Obrigatório quando 'Viagem de ida e volta' é verdadeiro."}
        )
    if campos["classe"] == "executiva" and not campos.get("justificativa_executiva"):
        raise DRFValidationError(
            {"justificativa_executiva": "Obrigatório quando a classe é Executiva."}
        )

    cpf = validate_cpf(campos["passageiro_cpf"])
    campos_limpos = {k: v for k, v in campos.items() if k != "passageiro_cpf"}
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=None)


def _validar_veiculo(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "tipo_veiculo", "data_hora_retirada", "data_hora_devolucao", "destino_rota",
        "estimativa_km", "motorista_incluso", "combustivel_incluso", "numero_passageiros",
    ])
    _choice(campos, "tipo_veiculo", _TIPO_VEICULO_CHOICES)
    _positivo(campos, "estimativa_km")
    _positivo(campos, "numero_passageiros")

    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _validar_grafico(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, ["tipo_material", "quantidade", "especificacoes_tecnicas", "prazo_entrega"])
    _choice(campos, "tipo_material", _TIPO_MATERIAL_CHOICES)
    _positivo(campos, "quantidade")
    _parse_date(campos["prazo_entrega"])

    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade_evento", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _validar_alimentacao(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, ["tipo_refeicao", "data_horario_servico", "numero_pessoas"])
    _choice(campos, "tipo_refeicao", _TIPO_REFEICAO_CHOICES)
    _positivo(campos, "numero_pessoas")

    campos_limpos = dict(campos)
    if not campos_limpos.get("local_entrega"):
        comunidade = getattr(activity, "comunidade", None)
        campos_limpos["local_entrega"] = comunidade.nome if comunidade else activity.municipio.nome
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _validar_equipamento(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "descricao_equipamento", "especificacao_tecnica_detalhada", "quantidade",
        "finalidade_justificativa", "urgencia",
    ])
    _choice(campos, "urgencia", _URGENCIA_CHOICES)
    _positivo(campos, "quantidade")

    return CamposValidados(campos_json=dict(campos), beneficiario_cpf=None, valor_estimado_auto=None)


_VALIDADORES = {
    "diaria": _validar_diaria,
    "passagem": _validar_passagem,
    "veiculo": _validar_veiculo,
    "grafico": _validar_grafico,
    "alimentacao": _validar_alimentacao,
    "equipamento": _validar_equipamento,
}


def validar_campos_json(tipo: str, campos: dict, activity) -> CamposValidados:
    validador = _VALIDADORES.get(tipo)
    if validador is None:
        raise DRFValidationError({"tipo": f"Tipo de solicitação desconhecido: '{tipo}'."})
    if not isinstance(campos, dict):
        raise DRFValidationError({"campos_json": "Deve ser um objeto JSON."})
    return validador(campos, activity)
