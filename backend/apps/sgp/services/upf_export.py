"""Dataset de exportação de UPFs, com os mesmos filtros da listagem."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.core.sensitive_fields import mascarar_cpf, pode_ver_cpf_completo
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.filters import UPFFilter
from apps.sgp.models import UPF, ExportJob
from apps.sgp.services.access import scope_queryset

# Até este total o arquivo é devolvido na própria requisição; acima, vira
# ExportJob processado pelo worker.
UPF_EXPORT_SYNC_LIMIT = 1000

EXPORT_COLUMNS = (
    ("estado", "Estado"),
    ("municipio", "Município"),
    ("territorio", "Território"),
    ("comunidade", "Comunidade"),
    ("titular", "Titular"),
    ("cpf", "CPF"),
    ("data_cadastro", "Data de cadastro"),
)

# Débito técnico: o front ainda envia `ativa` (nome anterior do campo `ativo`
# da UPF). Aceito como sinônimo só na exportação, onde parâmetro desconhecido
# é 400; sai quando o front passar a enviar `ativo`.
ALIASES_DE_FILTRO = {"ativa": "ativo"}


def separar_parametros(params: dict) -> tuple[str, dict]:
    """Valida os parâmetros da exportação e devolve `(formato, filtros)`.

    Só aceita os filtros declarados no `UPFFilter` (os mesmos da listagem):
    um parâmetro desconhecido seria ignorado pelo django-filter e geraria a
    base inteira em silêncio."""
    filtros = dict(params)
    formato = filtros.pop("formato", None) or ExportJob.Formato.CSV
    if formato not in ExportJob.Formato.values:
        raise serializers.ValidationError(
            {"formato": f"Use um de: {', '.join(ExportJob.Formato.values)}."}
        )

    for alias, nome in ALIASES_DE_FILTRO.items():
        if alias in filtros:
            valor = filtros.pop(alias)
            filtros.setdefault(nome, valor)

    desconhecidos = sorted(set(filtros) - set(UPFFilter.base_filters))
    if desconhecidos:
        raise ErroComCodigo(
            "parametro_desconhecido",
            "Parâmetro(s) não aceito(s) na exportação: " + ", ".join(desconhecidos) + ".",
            parametros=desconhecidos,
        )
    return formato, filtros


def upf_export_queryset(*, user, filtros: dict):
    qs = scope_queryset(
        UPF.all_objects.select_related(
            "municipio", "municipio__state", "territorio", "comunidade", "titular",
        ),
        user,
        state_lookup="municipio__state__sigla__in",
        territory_lookup="territorio__in",
        deny_message="Você não tem acesso ao módulo SGP.",
    )
    filterset = UPFFilter(data=filtros, queryset=qs)
    if not filterset.is_valid():
        raise serializers.ValidationError(filterset.errors)
    qs = filterset.qs
    # Mesmo padrão de `UPFViewSet.filter_queryset`: sem `ativo` na query, só ativas.
    if "ativo" not in filtros:
        qs = qs.filter(ativo=True)
    return qs.order_by("-criado_em", "-pk")


def upf_export_rows(queryset, *, user) -> list[dict[str, str]]:
    cpf_completo = pode_ver_cpf_completo(user)
    return [_serialize(upf, cpf_completo) for upf in queryset]


def _serialize(upf: UPF, cpf_completo: bool) -> dict[str, str]:
    cpf = upf.titular.cpf or ""
    return {
        "estado": upf.municipio.state.sigla,
        "municipio": upf.municipio.nome,
        "territorio": upf.territorio.nome if upf.territorio_id else "",
        "comunidade": upf.comunidade.nome if upf.comunidade_id else "",
        "titular": upf.titular.nome_completo,
        "cpf": cpf if cpf_completo else mascarar_cpf(cpf),
        "data_cadastro": timezone.localtime(upf.criado_em).date().isoformat(),
    }
