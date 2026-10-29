from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import models

from apps.core.models.municipality import Municipality
from apps.core.utils import get_config
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.constants import (
    Classe,
    MeioTransporte,
    TipoMaterial,
    TipoRefeicao,
    TipoVeiculo,
    Urgencia,
    Vinculo,
)
from apps.sgd.models.demand_type_rubrica_mapping import DemandTypeRubricaMapping
from apps.sgp.models import BudgetRubrica
from apps.sgp import validators as sgp_validators


@dataclass
class CamposValidados:
    campos_json: dict
    beneficiario_cpf: str | None
    valor_estimado_auto: Decimal | None


def rubrica_para_tipo(tipo: str) -> BudgetRubrica:
    """Rubrica do mapeamento ativo do tipo (config do Super Admin, SGD-RF05)."""
    mapeamento = DemandTypeRubricaMapping.objects.select_related("rubrica").filter(tipo=tipo, ativo=True).first()
    if mapeamento is None:
        raise RegraDeNegocio(f"Nenhuma rubrica mapeada para o tipo '{tipo}'. Configure em Super Admin.", campo="tipo")
    return mapeamento.rubrica


def _obrigatorios(campos: dict, nomes: list[str]) -> None:
    faltando = [n for n in nomes if campos.get(n) in (None, "")]
    if faltando:
        raise RegraDeNegocio(f"Campos obrigatórios ausentes: {', '.join(faltando)}.", campo="campos_json")


def _choice(campos: dict, campo: str, choices: type[models.TextChoices]) -> None:
    if campos.get(campo) not in choices.values:
        raise RegraDeNegocio(f"Valor inválido. Esperado um de: {sorted(choices.values)}.", campo=campo)


def _positivo(campos: dict, campo: str) -> None:
    try:
        valor = int(campos[campo])
    except (TypeError, ValueError):
        raise RegraDeNegocio("Deve ser um número inteiro.", campo=campo)
    if valor <= 0:
        raise RegraDeNegocio("Deve ser maior que zero.", campo=campo)


def _cpf(campos: dict, campo: str) -> str:
    # O validador é do SGP e levanta o erro do DRF; aqui ele vira erro do campo.
    try:
        return sgp_validators.validate_cpf(campos[campo])
    except sgp_validators.serializers.ValidationError as exc:
        raise RegraDeNegocio(str(exc.detail[0]), campo=campo) from exc


def _parse_date(valor) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise RegraDeNegocio(f"Data inválida: {valor!r}.", campo="data")


def _parse_decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        raise RegraDeNegocio(f"Valor decimal inválido: {valor!r}.", campo="valor")


@dataclass
class Diarias:
    numero: int
    valor_por_diaria: Decimal
    valor_total: Decimal


def calcular_diarias(*, municipio_destino_id, data_inicio, data_fim) -> Diarias:
    """Usada ao gravar a solicitação de diárias e na simulação do formulário, para
    as duas darem sempre o mesmo valor."""
    try:
        existe = Municipality.objects.filter(pk=municipio_destino_id).exists()
    except (TypeError, ValueError):
        existe = False
    if not existe:
        raise RegraDeNegocio("Município não encontrado.", campo="municipio_destino_id")
    inicio = _parse_date(data_inicio)
    fim = _parse_date(data_fim)
    if fim < inicio:
        raise RegraDeNegocio("Não pode ser anterior à data de início.", campo="data_fim")

    numero = max((fim - inicio).days, 1)
    valor_por_diaria = _parse_decimal(get_config("sgd_valor_diaria_padrao", "0"))
    if valor_por_diaria <= 0:
        raise RegraDeNegocio(
            "Valor de diária não configurado — contate o Super Admin (sgd_valor_diaria_padrao).",
            campo="valor_por_diaria",
        )
    return Diarias(numero=numero, valor_por_diaria=valor_por_diaria, valor_total=numero * valor_por_diaria)


def _validar_diaria(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "beneficiario_nome", "beneficiario_cpf", "beneficiario_cargo",
        "beneficiario_vinculo", "municipio_destino_id", "data_inicio",
        "data_fim", "meio_transporte", "justificativa",
    ])
    _choice(campos, "beneficiario_vinculo", Vinculo)
    _choice(campos, "meio_transporte", MeioTransporte)
    diarias = calcular_diarias(
        municipio_destino_id=campos["municipio_destino_id"],
        data_inicio=campos["data_inicio"], data_fim=campos["data_fim"],
    )
    cpf = _cpf(campos, "beneficiario_cpf")

    campos_limpos = {k: v for k, v in campos.items() if k != "beneficiario_cpf"}
    campos_limpos.update({
        "numero_diarias": diarias.numero,
        "valor_por_diaria": str(diarias.valor_por_diaria),
        "valor_total": str(diarias.valor_total),
    })
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=diarias.valor_total)


def _validar_passagem(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "passageiro_nome", "passageiro_cpf", "passageiro_data_nascimento",
        "aeroporto_origem", "aeroporto_destino", "data_hora_ida", "ida_e_volta",
        "bagagem_despachada", "classe", "urgencia",
    ])
    _choice(campos, "classe", Classe)
    _choice(campos, "urgencia", Urgencia)
    if not isinstance(campos["ida_e_volta"], bool):
        # `1 in (True, False)` é True em Python (1 == True) — checar o tipo
        # direto, não só o valor, senão 1/0 passariam pela checagem "estrita".
        raise RegraDeNegocio("Deve ser um booleano.", campo="ida_e_volta")

    if campos["ida_e_volta"] and not campos.get("data_hora_volta"):
        raise RegraDeNegocio("Obrigatório quando 'Viagem de ida e volta' é verdadeiro.", campo="data_hora_volta")
    if campos["classe"] == "executiva" and not campos.get("justificativa_executiva"):
        raise RegraDeNegocio("Obrigatório quando a classe é Executiva.", campo="justificativa_executiva")

    cpf = _cpf(campos, "passageiro_cpf")
    campos_limpos = {k: v for k, v in campos.items() if k != "passageiro_cpf"}
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=None)


def _validar_veiculo(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, [
        "tipo_veiculo", "data_hora_retirada", "data_hora_devolucao", "destino_rota",
        "estimativa_km", "motorista_incluso", "combustivel_incluso", "numero_passageiros",
    ])
    _choice(campos, "tipo_veiculo", TipoVeiculo)
    _positivo(campos, "estimativa_km")
    _positivo(campos, "numero_passageiros")

    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _validar_grafico(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, ["tipo_material", "quantidade", "especificacoes_tecnicas", "prazo_entrega"])
    _choice(campos, "tipo_material", TipoMaterial)
    _positivo(campos, "quantidade")
    _parse_date(campos["prazo_entrega"])

    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade_evento", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _validar_alimentacao(campos: dict, activity) -> CamposValidados:
    _obrigatorios(campos, ["tipo_refeicao", "data_horario_servico", "numero_pessoas"])
    _choice(campos, "tipo_refeicao", TipoRefeicao)
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
    _choice(campos, "urgencia", Urgencia)
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
        raise RegraDeNegocio(f"Tipo de solicitação desconhecido: '{tipo}'.", campo="tipo")
    if not isinstance(campos, dict):
        raise RegraDeNegocio("Deve ser um objeto JSON.", campo="campos_json")
    return validador(campos, activity)
