"""Campos de anexo do catálogo de tipos: `{"type": "integer", "format": "anexo"}` guarda
o id de um `DemandDocument` da demanda, e `{"type": "array", "items": {"type":
"integer", "format": "anexo"}}`, uma lista deles. O arquivo sobe pelo fluxo de
documentos da demanda, com `tipo="anexo"`; aqui ele é conferido e ligado à
solicitação e ao campo."""
from __future__ import annotations

from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.demand_document import DemandDocument

FORMATO = "anexo"
TIPO_DOCUMENTO = "anexo"


def _e_anexo(subschema) -> bool:
    return isinstance(subschema, dict) and subschema.get("format") == FORMATO


def campos_de_anexo(schema) -> dict[str, bool]:
    """Campos de anexo do schema, cada um com `True` se aceita vários arquivos.
    Só as `properties` de primeiro nível: são elas que viram campos do formulário."""
    propriedades = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(propriedades, dict):
        return {}
    campos = {}
    for nome, subschema in propriedades.items():
        if _e_anexo(subschema):
            campos[nome] = False
        elif isinstance(subschema, dict) and subschema.get("type") == "array" and _e_anexo(subschema.get("items")):
            campos[nome] = True
    return campos


def declaracoes_invalidas(schema) -> list[str]:
    """Campos de primeiro nível com `format: anexo` cujo valor não seria um id de documento."""
    propriedades = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(propriedades, dict):
        return []
    invalidos = []
    for nome, subschema in propriedades.items():
        if _e_anexo(subschema) and subschema.get("type") != "integer":
            invalidos.append(nome)
        elif isinstance(subschema, dict) and _e_anexo(subschema.get("items")):
            if subschema.get("type") != "array" or subschema["items"].get("type") != "integer":
                invalidos.append(nome)
    return invalidos


def ids_do_campo(valor, *, multiplo: bool) -> list[int]:
    """Ids informados no campo; vazio é campo não preenchido. O tipo já foi conferido pelo schema."""
    if valor in (None, "", []):
        return []
    return list(valor) if multiplo else [valor]


def _ids_por_campo(solicitacao) -> dict[str, list[int]]:
    campos = campos_de_anexo(solicitacao.tipo.schema_campos)
    return {
        campo: ids_do_campo(solicitacao.campos_json.get(campo), multiplo=multiplo)
        for campo, multiplo in campos.items()
    }


def vincular_anexos(solicitacao) -> None:
    """Confere os documentos citados nos campos de anexo e os liga à solicitação e ao
    campo. Os que deixaram de ser citados voltam a ser só documentos da demanda.
    Roda com a demanda travada pelo serviço que grava a solicitação."""
    campo_do_documento: dict[int, str] = {}
    for campo, ids in _ids_por_campo(solicitacao).items():
        for doc_id in ids:
            if doc_id in campo_do_documento:
                raise RegraDeNegocio("O mesmo documento foi informado mais de uma vez.", campo=campo)
            campo_do_documento[doc_id] = campo

    documentos = DemandDocument.objects.filter(pk__in=campo_do_documento).in_bulk()
    for doc_id, campo in campo_do_documento.items():
        documento = documentos.get(doc_id)
        if (
            documento is None or documento.demanda_id != solicitacao.demanda_id
            or not documento.ativo or documento.tipo != TIPO_DOCUMENTO
        ):
            raise RegraDeNegocio("Anexo não encontrado nesta demanda. Envie o arquivo de novo.", campo=campo)
        if documento.solicitacao_id not in (None, solicitacao.pk):
            raise RegraDeNegocio("Este anexo já está em outra solicitação da demanda.", campo=campo)

    DemandDocument.objects.filter(solicitacao=solicitacao).exclude(pk__in=campo_do_documento).update(
        solicitacao=None, campo="",
    )
    for doc_id, campo in campo_do_documento.items():
        documento = documentos[doc_id]
        if documento.solicitacao_id != solicitacao.pk or documento.campo != campo:
            documento.solicitacao = solicitacao
            documento.campo = campo
            documento.save(update_fields=["solicitacao", "campo"])


def exigir_anexos_ativos(demand) -> None:
    """Um anexo removido da aba de documentos depois de informado no campo barra a submissão."""
    ativos = set(
        DemandDocument.objects.filter(solicitacao__demanda=demand, ativo=True).values_list("solicitacao_id", "pk")
    )
    for solicitacao in demand.solicitacoes.select_related("tipo").order_by("ordem", "pk"):
        for campo, ids in _ids_por_campo(solicitacao).items():
            if any((solicitacao.pk, doc_id) not in ativos for doc_id in ids):
                raise RegraDeNegocio("Um anexo deste campo foi removido. Envie o arquivo de novo.", campo=campo)
