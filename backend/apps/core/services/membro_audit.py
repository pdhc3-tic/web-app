"""
AuditLog centralizado para alterações em MembroFamilia (titular ou membro
comum), usado por SGP, UPF e SCA. Nunca registra o valor de saude/cor_raca —
só `campos_alterados`, os nomes que mudaram.
"""

from __future__ import annotations

from apps.core.services.audit import log_audit

SENSITIVE_MEMBRO_FIELDS = ("saude", "cor_raca")


def sensitive_fields_changed(anteriores: dict | None, novos: dict) -> list[str]:
    """Campos de SENSITIVE_MEMBRO_FIELDS que mudaram de `anteriores` para
    `novos` (dicts como `{"saude": [...], "cor_raca": ...}`, subconjunto ok).
    `anteriores=None` (criação): conta como alterado se veio preenchido.
    """
    alterados = []
    for field in SENSITIVE_MEMBRO_FIELDS:
        if field not in novos:
            continue
        novo_valor = novos[field]
        if anteriores is None:
            if novo_valor not in (None, [], ""):
                alterados.append(field)
        elif anteriores.get(field) != novo_valor:
            alterados.append(field)
    return alterados


def log_membro_change(
    *,
    user,
    acao: str,
    membro,
    origem: str,
    campos_alterados: list[str],
    request=None,
    valores_anteriores: dict | None = None,
    extra_novos: dict | None = None,
):
    valores_novos = {
        "membro_id": membro.pk,
        "nome_completo": membro.nome_completo,
        "grau_parentesco": membro.grau_parentesco,
        "upf_id": membro.upf_id,
        "origem": origem,
        "campos_alterados": campos_alterados,
    }
    if extra_novos:
        valores_novos.update(extra_novos)

    return log_audit(
        user=user,
        acao=acao,
        modulo="sgp",
        entidade="MembroFamilia",
        entidade_id=membro.pk,
        valores_anteriores=valores_anteriores or {},
        valores_novos=valores_novos,
        request=request,
    )
