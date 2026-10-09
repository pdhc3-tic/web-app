"""Mapeamento de campos Arlo <-> SGD (SGD-RF31/RF32), lido de `ArloFieldMapping`.

O Super Admin edita o mapeamento em /api/v1/sgd/config/arlo-mapping/. O
MAPEAMENTO_PADRAO só vale enquanto não houver nenhuma linha ativa na direção.
"""
from datetime import date, datetime
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from apps.sgd.models.arlo_field_mapping import ArloFieldMapping

EXPORTACAO = ArloFieldMapping.Direcao.EXPORTACAO
IMPORTACAO = ArloFieldMapping.Direcao.IMPORTACAO
TEXTO = ArloFieldMapping.Formato.TEXTO
DATA = ArloFieldMapping.Formato.DATA
MOEDA = ArloFieldMapping.Formato.MOEDA

CAMPOS_EXPORTACAO = {
    "demanda_id", "solicitacao_id", "titulo", "meta", "submeta", "acao", "indicador",
    "atividade", "rubrica", "solicitante", "valor_estimado", "valor_autorizado",
}
# Colunas que a issue exige na exportação (SGD-RF31) — não podem ficar de fora.
CAMPOS_EXPORTACAO_OBRIGATORIOS = {"demanda_id", "meta", "submeta", "acao", "indicador", "atividade", "rubrica"}

CAMPOS_IMPORTACAO = {"demanda_id", "solicitacao_id", "numero_processo", "data_pagamento", "valor_pago", "comprovante"}
CAMPOS_IMPORTACAO_OBRIGATORIOS = {"demanda_id", "numero_processo", "data_pagamento", "valor_pago"}

CAMPOS = {EXPORTACAO: CAMPOS_EXPORTACAO, IMPORTACAO: CAMPOS_IMPORTACAO}
CAMPOS_OBRIGATORIOS = {EXPORTACAO: CAMPOS_EXPORTACAO_OBRIGATORIOS, IMPORTACAO: CAMPOS_IMPORTACAO_OBRIGATORIOS}

# O tipo do dado é do campo, não da coluna: só os campos monetários aceitam
# `moeda` e só a data de pagamento aceita `data`; os demais são sempre texto.
# Na importação o parser depende do tipo, então não há como cair para `texto`.
CAMPOS_MOEDA = {"valor_estimado", "valor_autorizado", "valor_pago"}
CAMPOS_DATA = {"data_pagamento"}


def formatos_permitidos(direcao: str, campo: str) -> set[str]:
    if campo in CAMPOS_MOEDA:
        return {MOEDA} if direcao == IMPORTACAO else {TEXTO, MOEDA}
    if campo in CAMPOS_DATA:
        return {DATA} if direcao == IMPORTACAO else {TEXTO, DATA}
    return {TEXTO}


def formato_padrao(campo: str) -> str:
    if campo in CAMPOS_MOEDA:
        return MOEDA
    if campo in CAMPOS_DATA:
        return DATA
    return TEXTO


MAPEAMENTO_PADRAO = {
    "exportacao": [
        {"campo": "demanda_id", "coluna": "ID Demanda"},
        {"campo": "solicitacao_id", "coluna": "ID Solicitação"},
        {"campo": "titulo", "coluna": "Título"},
        {"campo": "meta", "coluna": "Meta"},
        {"campo": "submeta", "coluna": "Submeta"},
        {"campo": "acao", "coluna": "Ação"},
        {"campo": "indicador", "coluna": "Indicador"},
        {"campo": "atividade", "coluna": "Atividade"},
        {"campo": "rubrica", "coluna": "Rubrica"},
        {"campo": "valor_autorizado", "coluna": "Valor Autorizado"},
    ],
    "importacao": {
        "demanda_id": "ID Demanda",
        "solicitacao_id": "ID Solicitação",
        "numero_processo": "Número do Processo",
        "data_pagamento": "Data do Pagamento",
        "valor_pago": "Valor Pago",
        "comprovante": "Comprovante",
    },
}


def _padrao_exportacao() -> list[dict]:
    return [
        {"campo": item["campo"], "coluna": item["coluna"], "formato": formato_padrao(item["campo"])}
        for item in MAPEAMENTO_PADRAO["exportacao"]
    ]


def _padrao_importacao() -> dict:
    return {
        campo: {"coluna": coluna, "formato": formato_padrao(campo)}
        for campo, coluna in MAPEAMENTO_PADRAO["importacao"].items()
    }


def validar_mapeamento(mapeamento: dict) -> None:
    """Rede de segurança na leitura: um mapeamento sem os campos obrigatórios
    quebraria a exportação/importação só em produção."""
    faltando = CAMPOS_EXPORTACAO_OBRIGATORIOS - {item["campo"] for item in mapeamento["exportacao"]}
    if faltando:
        raise ValidationError(f"Campos obrigatórios ausentes na exportação: {sorted(faltando)}.")
    faltando = CAMPOS_IMPORTACAO_OBRIGATORIOS - set(mapeamento["importacao"])
    if faltando:
        raise ValidationError(f"Campos obrigatórios ausentes na importação: {sorted(faltando)}.")


def validar_ativos_obrigatorios(direcao: str, ativos: set[str]) -> None:
    """`ativos`: campos que ficariam ativos na direção após a alteração."""
    faltando = CAMPOS_OBRIGATORIOS[direcao] - ativos
    if faltando:
        raise ValidationError(
            f"Campos obrigatórios não podem ser removidos ou desativados: {sorted(faltando)}."
        )


def obter_mapeamento() -> dict:
    """Mapeamento vigente: {"exportacao": [{campo, coluna, formato}],
    "importacao": {campo: {coluna, formato}}}, só linhas ativas, por `ordem`."""
    linhas = list(ArloFieldMapping.objects.filter(ativo=True).order_by("ordem", "pk"))
    exportacao = [
        {"campo": m.campo_sgd, "coluna": m.coluna_arlo, "formato": m.formato}
        for m in linhas if m.direcao == EXPORTACAO
    ]
    importacao = {
        m.campo_sgd: {"coluna": m.coluna_arlo, "formato": m.formato}
        for m in linhas if m.direcao == IMPORTACAO
    }
    mapeamento = {
        "exportacao": exportacao or _padrao_exportacao(),
        "importacao": importacao or _padrao_importacao(),
    }
    validar_mapeamento(mapeamento)
    return mapeamento


def formatar_valor(valor, formato: str):
    """Aplica o `formato` configurado ao valor exportado."""
    if valor is None:
        return ""
    if formato == DATA and isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    if formato == MOEDA and isinstance(valor, (int, Decimal)):
        return f"{Decimal(valor):.2f}".replace(".", ",")
    return valor
