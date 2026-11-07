"""
Exportação CSV de membros — Issue #186.

Fonte única do dataset exportável, compartilhada pelas duas rotas:
  - export por UFPA específica (`MembroViewSet.exportar`)
  - export territorial agregado (`MembroExportView`)

As colunas sensíveis (`cor_raca`, `saude`) só entram no dataset quando o
usuário tem permissão de leitura sobre elas — mesma matriz usada pela API
(`apps.core.sensitive_fields`), para não haver duas fontes de verdade.
"""

from __future__ import annotations

from datetime import date

from apps.core.sensitive_fields import sensitive_fields_visible_to
from apps.sgp.constants import COR_RACA_CHOICES, GENERO_CHOICES
from apps.sgp.models import MembroFamilia
from apps.sgp.services.access import ufpas_acessiveis_ao_usuario

# Limite de UFPAs por exportação territorial agregada — protege contra
# arquivos excessivamente grandes. Acima disso, o chamador deve restringir
# por território, município ou projeto.
MEMBROS_EXPORT_UFPA_LIMIT = 500

BASE_EXPORT_COLUMNS = (
    ("id", "ID"),
    ("ufpa_id", "UFPA"),
    ("nome_completo", "Nome completo"),
    ("grau_parentesco", "Parentesco"),
    ("data_nascimento", "Data de nascimento"),
    ("idade", "Idade"),
    ("genero", "Gênero"),
    ("cpf", "CPF"),
    ("municipio", "Município"),
    ("territorio", "Território"),
    ("projeto", "Projeto"),
)

# Só entram no CSV se `sensitive_fields_visible_to(user)` autorizar o campo.
SENSITIVE_EXPORT_COLUMNS = (
    ("cor_raca", "Cor/Raça"),
    ("saude", "Condições de saúde"),
)

_COR_RACA_LABELS = dict(COR_RACA_CHOICES)
_GENERO_LABELS = dict(GENERO_CHOICES)


class ExportLimitExceeded(Exception):
    """Levantada quando o escopo territorial excede `MEMBROS_EXPORT_UFPA_LIMIT` UFPAs."""

    def __init__(self, ufpa_count: int, limit: int):
        self.ufpa_count = ufpa_count
        self.limit = limit
        super().__init__(
            f"Exportação abrange {ufpa_count} UFPAs, acima do limite de {limit}."
        )


def export_columns_for(user) -> list[tuple[str, str]]:
    """Colunas do CSV para este usuário: base + sensíveis que ele pode ler."""
    columns = list(BASE_EXPORT_COLUMNS)
    visible = sensitive_fields_visible_to(user)
    for key, label in SENSITIVE_EXPORT_COLUMNS:
        if key in visible:
            columns.append((key, label))
    return columns


def _idade(data_nascimento) -> str:
    if not data_nascimento:
        return ""
    hoje = date.today()
    anos = (
        hoje.year - data_nascimento.year
        - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
    )
    return str(anos)


def _row_for(membro: MembroFamilia, column_keys: set[str]) -> dict[str, str]:
    ufpa = membro.ufpa
    row = {
        "id": str(membro.pk),
        "ufpa_id": str(membro.ufpa_id) if membro.ufpa_id else "",
        "nome_completo": membro.nome_completo,
        "grau_parentesco": membro.get_grau_parentesco_display(),
        "data_nascimento": (
            membro.data_nascimento.isoformat() if membro.data_nascimento else ""
        ),
        "idade": _idade(membro.data_nascimento),
        "genero": _GENERO_LABELS.get(membro.genero, ""),
        "cpf": membro.cpf,
        "municipio": ufpa.municipio.nome if ufpa and ufpa.municipio_id else "",
        "territorio": ufpa.territorio.nome if ufpa and ufpa.territorio_id else "",
        "projeto": ufpa.projeto.nome if ufpa and ufpa.projeto_id else "",
    }
    if "cor_raca" in column_keys:
        row["cor_raca"] = _COR_RACA_LABELS.get(membro.cor_raca, "")
    if "saude" in column_keys:
        row["saude"] = "; ".join(membro.saude or [])
    return row


def _membros_queryset(filtro_ufpa):
    return (
        MembroFamilia.objects.filter(filtro_ufpa)
        .select_related("ufpa", "ufpa__municipio", "ufpa__territorio", "ufpa__projeto")
    )


def membro_export_rows_for_ufpa(ufpa, *, user):
    """Dataset de exportação para uma única UFPA (já resolvida e autorizada)."""
    from django.db.models import Q

    columns = export_columns_for(user)
    column_keys = {key for key, _ in columns}
    membros = _membros_queryset(Q(ufpa=ufpa)).order_by("nome_completo")
    rows = [_row_for(m, column_keys) for m in membros]
    return columns, rows


def membro_export_rows_for_scope(
    *,
    user,
    territorio_id: int | None = None,
    municipio_id: int | None = None,
    projeto_id: int | None = None,
):
    """
    Dataset de exportação agregado, restrito ao escopo territorial do
    usuário (mesma regra de `ufpas_acessiveis_ao_usuario`) e aos filtros
    informados. Levanta `ExportLimitExceeded` se o número de UFPAs no escopo
    filtrado exceder `MEMBROS_EXPORT_UFPA_LIMIT`.
    """
    from django.db.models import Q

    ufpas = ufpas_acessiveis_ao_usuario(user)
    if territorio_id is not None:
        ufpas = ufpas.filter(territorio_id=territorio_id)
    if municipio_id is not None:
        ufpas = ufpas.filter(municipio_id=municipio_id)
    if projeto_id is not None:
        ufpas = ufpas.filter(projeto_id=projeto_id)

    ufpa_count = ufpas.count()
    if ufpa_count > MEMBROS_EXPORT_UFPA_LIMIT:
        raise ExportLimitExceeded(ufpa_count, MEMBROS_EXPORT_UFPA_LIMIT)

    columns = export_columns_for(user)
    column_keys = {key for key, _ in columns}
    membros = _membros_queryset(Q(ufpa__in=ufpas)).order_by("ufpa_id", "nome_completo")
    rows = [_row_for(m, column_keys) for m in membros]
    return columns, rows
