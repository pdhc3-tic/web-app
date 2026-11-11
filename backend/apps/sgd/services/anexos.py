"""Campos de anexo do catálogo de tipos: `{"type": "integer", "format": "anexo"}` guarda
o id de um `DemandDocument` da demanda, e `{"type": "array", "items": {"type":
"integer", "format": "anexo"}}`, uma lista deles. O arquivo sobe pelo fluxo de
documentos da demanda, com `tipo="anexo"`; aqui ele é conferido e ligado à
solicitação e ao campo."""
from __future__ import annotations

from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.services import demand_document as demand_document_service

FORMATO = "anexo"
TIPO_DOCUMENTO = "anexo"


def _e_anexo(subschema) -> bool:
    return isinstance(subschema, dict) and subschema.get("format") == FORMATO


def _propriedades(schema) -> dict:
    propriedades = schema.get("properties") if isinstance(schema, dict) else None
    return propriedades if isinstance(propriedades, dict) else {}


def campos_de_anexo(schema) -> dict[str, bool]:
    """Campos de anexo do schema, cada um com `True` se aceita vários arquivos.
    Só as `properties` de primeiro nível: são elas que viram campos do formulário."""
    campos = {}
    for nome, subschema in _propriedades(schema).items():
        if _e_anexo(subschema):
            campos[nome] = False
        elif isinstance(subschema, dict) and subschema.get("type") == "array" and _e_anexo(subschema.get("items")):
            campos[nome] = True
    return campos


def declaracoes_invalidas(schema) -> list[str]:
    """Campos de primeiro nível com `format: anexo` cujo valor não seria um id de documento."""
    invalidos = []
    for nome, subschema in _propriedades(schema).items():
        if _e_anexo(subschema) and subschema.get("type") != "integer":
            invalidos.append(nome)
        elif isinstance(subschema, dict) and _e_anexo(subschema.get("items")):
            if subschema.get("type") != "array" or subschema["items"].get("type") != "integer":
                invalidos.append(nome)
    return invalidos


def _e_id(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def ids_do_campo(valor, *, multiplo: bool) -> list[int] | None:
    """Ids informados no campo; vazio é campo não preenchido. `None` quando o valor
    não tem a forma do campo: o schema do catálogo pode ter mudado depois da gravação."""
    if valor is None or valor == "" or valor == []:
        return []
    itens = valor if multiplo and isinstance(valor, list) else [valor] if not multiplo else None
    if itens is None or not all(_e_id(item) for item in itens):
        return None
    return itens


def _titulo(schema, campo: str) -> str:
    titulo = _propriedades(schema).get(campo, {}).get("title")
    return titulo if isinstance(titulo, str) and titulo else campo


def vincular_anexos(solicitacao, *, usuario=None) -> None:
    """Confere os documentos citados nos campos de anexo e os liga à solicitação e ao
    campo. O anexo que deixa de ser citado é removido, como na aba de documentos.
    Roda com a demanda travada pelo serviço que grava a solicitação."""
    schema = solicitacao.tipo.schema_campos
    obrigatorios = set(schema.get("required") or ())
    campo_do_documento: dict[int, str] = {}
    for campo, multiplo in campos_de_anexo(schema).items():
        ids = ids_do_campo(solicitacao.campos_json.get(campo), multiplo=multiplo)
        if ids is None:
            raise RegraDeNegocio("Deve ser o id de um anexo enviado.", campo=campo)
        if not ids and campo in obrigatorios:
            raise RegraDeNegocio("Obrigatório.", campo=campo)
        for doc_id in ids:
            if doc_id in campo_do_documento:
                raise RegraDeNegocio("O mesmo anexo foi informado mais de uma vez.", campo=campo)
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

    substituidos = DemandDocument.objects.filter(solicitacao=solicitacao, ativo=True).exclude(pk__in=campo_do_documento)
    for documento in substituidos:
        demand_document_service.remover(documento, usuario=usuario)
    for doc_id, campo in campo_do_documento.items():
        documento = documentos[doc_id]
        if documento.solicitacao_id != solicitacao.pk or documento.campo != campo:
            documento.solicitacao = solicitacao
            documento.campo = campo
            documento.save(update_fields=["solicitacao", "campo"])


def remover_anexos(solicitacao, *, usuario=None) -> None:
    """Na remoção da solicitação, os anexos dela saem junto."""
    for documento in DemandDocument.objects.filter(solicitacao=solicitacao, ativo=True):
        demand_document_service.remover(documento, usuario=usuario)


def exigir_anexos_ativos(demand) -> None:
    """Um anexo removido da aba de documentos depois de informado no campo, ou um valor
    que deixou de ter a forma do campo, barra a submissão."""
    ativos = set(
        DemandDocument.objects.filter(solicitacao__demanda=demand, ativo=True).values_list("solicitacao_id", "pk")
    )
    for solicitacao in demand.solicitacoes.select_related("tipo").order_by("ordem", "pk"):
        schema = solicitacao.tipo.schema_campos
        for campo, multiplo in campos_de_anexo(schema).items():
            ids = ids_do_campo(solicitacao.campos_json.get(campo), multiplo=multiplo)
            if ids is None or any((solicitacao.pk, doc_id) not in ativos for doc_id in ids):
                raise RegraDeNegocio(
                    f'Um anexo de "{_titulo(schema, campo)}" na solicitação de {solicitacao.tipo.nome} '
                    "foi removido. Envie o arquivo de novo.",
                    campo=campo,
                )
