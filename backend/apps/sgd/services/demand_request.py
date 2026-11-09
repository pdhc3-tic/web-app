from __future__ import annotations

from datetime import date

from apps.core.models.municipality import Municipality
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.models.tipo_solicitacao import TipoSolicitacao
from apps.sgd.services import diarias as diarias_service
from apps.sgd.services.diarias import CalculoDiarias
from apps.sgd.services.tipos_solicitacao import (
    CamposValidados,
    obter_validador,
    registrar_validador,
    validar_por_schema,
)
from apps.sgp.models import BudgetRubrica
from apps.sgp import validators as sgp_validators


def rubrica_para_tipo(tipo: str) -> BudgetRubrica:
    """Rubrica do tipo no catálogo. Tipo inativo não aceita solicitação nova."""
    catalogo = TipoSolicitacao.objects.select_related("rubrica").filter(slug=tipo, ativo=True).first()
    if catalogo is None:
        raise RegraDeNegocio(f"Nenhuma rubrica mapeada para o tipo '{tipo}'. Configure em Super Admin.", campo="tipo")
    return catalogo.rubrica


def _cpf(campos: dict, campo: str) -> str:
    _exigir_campos(campos, campo)
    if not isinstance(campos[campo], str):
        raise RegraDeNegocio("Deve ser um texto com os dígitos do CPF.", campo=campo)
    # O validador é do SGP e levanta o erro do DRF; aqui ele vira erro do campo.
    try:
        return sgp_validators.validate_cpf(campos[campo])
    except sgp_validators.serializers.ValidationError as exc:
        raise RegraDeNegocio(str(exc.detail[0]), campo=campo) from exc


def _exigir_campos(campos: dict, *nomes: str) -> None:
    # O schema do catálogo é editável; a estratégia ainda precisa destes valores.
    for nome in nomes:
        if campos.get(nome) in (None, ""):
            raise RegraDeNegocio("Obrigatório.", campo=nome)


def _parse_date(valor) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise RegraDeNegocio(f"Data inválida: {valor!r}.", campo="data")


def _parse_bool(valor, campo: str) -> bool:
    if valor in (None, ""):
        return False
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in ("true", "1", "sim"):
        return True
    if texto in ("false", "0", "nao", "não"):
        return False
    raise RegraDeNegocio("Deve ser verdadeiro ou falso.", campo=campo)


def calcular_diarias(*, municipio_destino_id, data_inicio, data_fim, hospedagem_custeada=False) -> CalculoDiarias:
    """Usada ao gravar a solicitação de diárias e na simulação do formulário, para
    as duas darem sempre o mesmo valor."""
    try:
        municipio = Municipality.objects.filter(pk=municipio_destino_id).first()
    except (TypeError, ValueError):
        municipio = None
    if municipio is None:
        raise RegraDeNegocio("Município não encontrado.", campo="municipio_destino_id")
    inicio = _parse_date(data_inicio)
    fim = _parse_date(data_fim)
    if fim < inicio:
        raise RegraDeNegocio("Não pode ser anterior à data de início.", campo="data_fim")
    return diarias_service.calcular(
        municipio=municipio, data_inicio=inicio, data_fim=fim,
        hospedagem_custeada=_parse_bool(hospedagem_custeada, "hospedagem_custeada"),
    )


@registrar_validador("diaria", chave_cpf="beneficiario_cpf")
def _validar_diaria(campos: dict, activity) -> CamposValidados:
    _exigir_campos(campos, "municipio_destino_id", "data_inicio", "data_fim", "beneficiario_cpf")
    hospedagem_custeada = _parse_bool(campos.get("hospedagem_custeada"), "hospedagem_custeada")
    diarias = calcular_diarias(
        municipio_destino_id=campos["municipio_destino_id"],
        data_inicio=campos["data_inicio"], data_fim=campos["data_fim"],
        hospedagem_custeada=hospedagem_custeada,
    )
    cpf = _cpf(campos, "beneficiario_cpf")

    # Valores congelados: alterar a tabela depois não muda a solicitação gravada.
    campos_limpos = {k: v for k, v in campos.items() if k != "beneficiario_cpf"}
    campos_limpos.update({
        "hospedagem_custeada": hospedagem_custeada,
        "faixa_destino": {"id": diarias.faixa.pk, "nome": diarias.faixa.nome},
        "tabela_diaria_id": diarias.tabela.pk,
        "valor_por_diaria": str(diarias.valor_por_diaria),
        "numero_diarias": str(diarias.numero),
        "adicional_embarque": str(diarias.adicional_embarque),
        "valor_total": str(diarias.valor_total),
    })
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=diarias.valor_total)


@registrar_validador("passagem", chave_cpf="passageiro_cpf")
def _validar_passagem(campos: dict, activity) -> CamposValidados:
    cpf = _cpf(campos, "passageiro_cpf")
    campos_limpos = {k: v for k, v in campos.items() if k != "passageiro_cpf"}
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=cpf, valor_estimado_auto=None)


@registrar_validador("veiculo")
def _validar_veiculo(campos: dict, activity) -> CamposValidados:
    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


@registrar_validador("grafico")
def _validar_grafico(campos: dict, activity) -> CamposValidados:
    campos_limpos = dict(campos)
    campos_limpos.setdefault("finalidade_evento", activity.descricao_narrativa)
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


@registrar_validador("alimentacao")
def _validar_alimentacao(campos: dict, activity) -> CamposValidados:
    campos_limpos = dict(campos)
    if not campos_limpos.get("local_entrega"):
        comunidade = getattr(activity, "comunidade", None)
        campos_limpos["local_entrega"] = comunidade.nome if comunidade else activity.municipio.nome
    return CamposValidados(campos_json=campos_limpos, beneficiario_cpf=None, valor_estimado_auto=None)


def _exigir_minimo_cotacoes_equipamento(demand) -> None:
    if not demand.solicitacoes.filter(tipo__validador="equipamento").exists():
        return
    fornecedores = list(
        DemandDocument.objects.filter(demanda=demand, tipo="cotacao", ativo=True)
        .values_list("fornecedor", flat=True)
    )
    if len(fornecedores) < 3:
        raise RegraDeNegocio(
            "Solicitação de Aquisição de Equipamentos exige no mínimo 3 cotações em PDF.", campo="documentos",
        )
    if len(set(fornecedores)) < len(fornecedores):
        raise RegraDeNegocio("As cotações precisam ser de fornecedores distintos.", campo="documentos")


@registrar_validador("equipamento", ao_submeter=_exigir_minimo_cotacoes_equipamento)
def _validar_equipamento(campos: dict, activity) -> CamposValidados:
    return CamposValidados(campos_json=dict(campos), beneficiario_cpf=None, valor_estimado_auto=None)


def validar_campos_json(tipo: str, campos: dict, activity) -> CamposValidados:
    catalogo = TipoSolicitacao.objects.filter(slug=tipo).first()
    if catalogo is None:
        raise RegraDeNegocio(f"Tipo de solicitação desconhecido: '{tipo}'.", campo="tipo")
    if not isinstance(campos, dict):
        raise RegraDeNegocio("Deve ser um objeto JSON.", campo="campos_json")
    validar_por_schema(catalogo.schema_campos, campos)
    validador = obter_validador(catalogo.validador)
    if validador is None:
        return CamposValidados(campos_json=dict(campos), beneficiario_cpf=None, valor_estimado_auto=None)
    return validador.preparar(campos, activity)


def exigir_regras_de_submissao(demand) -> None:
    nomes = set(demand.solicitacoes.values_list("tipo__validador", flat=True))
    for nome in sorted(nomes):
        validador = obter_validador(nome)
        if validador is not None and validador.ao_submeter is not None:
            validador.ao_submeter(demand)
