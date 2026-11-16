"""Dataset de exportação de UFPAs, com os mesmos filtros da listagem."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.core.sensitive_fields import mascarar_cpf, pode_ver_cpf_completo
from apps.sgp.exceptions import recusar_parametros_desconhecidos
from apps.sgp.filters import UFPAFilter, somente_ativas_sem_filtro_ativo
from apps.sgp.models import UFPA, ExportJob
from apps.sgp.services.access import ufpas_acessiveis_ao_usuario

EXPORT_COLUMNS = (
    ("estado", "Estado"),
    ("municipio", "Município"),
    ("territorio", "Território"),
    ("comunidade", "Comunidade"),
    ("titular", "Titular"),
    ("cpf", "CPF"),
    ("data_cadastro", "Data de cadastro"),
)

FILTROS_ACEITOS = frozenset(UFPAFilter.base_filters)


def separar_parametros(params: dict) -> tuple[str, dict]:
    """Valida os parâmetros da exportação e devolve `(formato, filtros)`.

    Só aceita os filtros declarados no `UFPAFilter` (os mesmos da listagem):
    um parâmetro desconhecido seria ignorado pelo django-filter e geraria a
    base inteira em silêncio."""
    filtros = dict(params)
    formato = filtros.pop("formato", None) or ExportJob.Formato.CSV
    if formato not in ExportJob.Formato.values:
        raise serializers.ValidationError(
            {"formato": f"Use um de: {', '.join(ExportJob.Formato.values)}."}
        )

    recusar_parametros_desconhecidos(filtros, FILTROS_ACEITOS)
    # Valida os valores já aqui, sem consultar o banco, para que o pedido
    # assíncrono seja recusado na criação e não só dentro do job.
    _filterset(filtros, UFPA.objects.none())
    return formato, filtros


def _filterset(filtros: dict, queryset) -> UFPAFilter:
    filterset = UFPAFilter(data=filtros, queryset=queryset)
    if not filterset.is_valid():
        raise serializers.ValidationError(filterset.errors)
    return filterset


def ufpa_export_queryset(*, user, filtros: dict):
    queryset = ufpas_acessiveis_ao_usuario(user, raise_on_no_role=True).select_related(
        "municipio", "municipio__state", "territorio", "comunidade", "titular",
    )
    queryset = somente_ativas_sem_filtro_ativo(_filterset(filtros, queryset).qs, filtros)
    return queryset.order_by("-criado_em", "-pk")


def ufpa_export_rows(queryset, *, user) -> list[dict[str, str]]:
    cpf_completo = pode_ver_cpf_completo(user)
    return [_serialize(ufpa, cpf_completo) for ufpa in queryset]


def _serialize(ufpa: UFPA, cpf_completo: bool) -> dict[str, str]:
    cpf = ufpa.titular.cpf or ""
    return {
        "estado": ufpa.municipio.state.sigla,
        "municipio": ufpa.municipio.nome,
        "territorio": ufpa.territorio.nome if ufpa.territorio_id else "",
        "comunidade": ufpa.comunidade.nome if ufpa.comunidade_id else "",
        "titular": ufpa.titular.nome_completo,
        "cpf": cpf if cpf_completo else mascarar_cpf(cpf),
        "data_cadastro": timezone.localtime(ufpa.criado_em).date().isoformat(),
    }
