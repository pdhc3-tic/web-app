"""Mapeamento de campos Arlo <-> SGD (SGD-RF31/RF32), lido do SystemConfig.

O Super Admin edita a chave `sgd_arlo_mapeamento_campos` pelo painel de
configuração; o MAPEAMENTO_PADRAO só vale se a chave ainda não existir.
"""
from rest_framework.exceptions import ValidationError

from apps.core.utils import get_config

CHAVE_MAPEAMENTO = "sgd_arlo_mapeamento_campos"

CAMPOS_EXPORTACAO = {
    "demanda_id", "solicitacao_id", "titulo", "meta", "submeta", "acao", "indicador",
    "atividade", "rubrica", "solicitante", "valor_estimado", "valor_autorizado",
}
# Colunas que a issue exige na exportação (SGD-RF31) — não podem ficar de fora.
CAMPOS_EXPORTACAO_OBRIGATORIOS = {"demanda_id", "meta", "submeta", "acao", "indicador", "atividade", "rubrica"}

CAMPOS_IMPORTACAO = {"demanda_id", "solicitacao_id", "numero_processo", "data_pagamento", "valor_pago", "comprovante"}
CAMPOS_IMPORTACAO_OBRIGATORIOS = {"demanda_id", "numero_processo", "data_pagamento", "valor_pago"}

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


def validar_mapeamento(mapeamento) -> None:
    """Usado no PATCH do SystemConfig e na leitura — mapeamento inválido
    quebraria a exportação/importação só em produção."""
    if not isinstance(mapeamento, dict):
        raise ValidationError("Mapeamento Arlo deve ser um objeto com 'exportacao' e 'importacao'.")

    exportacao = mapeamento.get("exportacao")
    if not isinstance(exportacao, list) or not all(
        isinstance(item, dict) and item.get("campo") in CAMPOS_EXPORTACAO and item.get("coluna")
        for item in exportacao
    ):
        raise ValidationError(
            f"'exportacao' deve ser uma lista de {{campo, coluna}} com campo em {sorted(CAMPOS_EXPORTACAO)}."
        )
    faltando = CAMPOS_EXPORTACAO_OBRIGATORIOS - {item["campo"] for item in exportacao}
    if faltando:
        raise ValidationError(f"Campos obrigatórios ausentes na exportação: {sorted(faltando)}.")

    importacao = mapeamento.get("importacao")
    if not isinstance(importacao, dict) or not set(importacao) <= CAMPOS_IMPORTACAO or not all(
        isinstance(coluna, str) and coluna for coluna in importacao.values()
    ):
        raise ValidationError(f"'importacao' deve mapear campos em {sorted(CAMPOS_IMPORTACAO)} para nomes de coluna.")
    faltando = CAMPOS_IMPORTACAO_OBRIGATORIOS - set(importacao)
    if faltando:
        raise ValidationError(f"Campos obrigatórios ausentes na importação: {sorted(faltando)}.")


def obter_mapeamento() -> dict:
    mapeamento = get_config(CHAVE_MAPEAMENTO, default=MAPEAMENTO_PADRAO)
    validar_mapeamento(mapeamento)
    return mapeamento
