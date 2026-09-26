"""Dataset consolidado de Atividades de Campo para exportação."""

from __future__ import annotations

from datetime import date

from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.sgp.models import Activity
from apps.sgp.services.access import scope_queryset

EXPORT_COLUMNS = (
    ("id", "ID"),
    ("titulo", "Título"),
    ("tipo_atividade", "Tipo"),
    ("status", "Status"),
    ("data_inicio", "Data de início"),
    ("data_fim", "Data de fim"),
    ("estado", "Estado"),
    ("municipio", "Município"),
    ("territorio", "Território"),
    ("comunidade", "Comunidade"),
    ("meta", "Meta"),
    ("acao", "Ação"),
    ("tecnico_responsavel", "Técnico responsável"),
    ("total_upfs", "UPFs participantes"),
    ("total_participantes", "Participantes"),
    ("atrasada", "Atrasada"),
)


def _contagem_m2m(through):
    # Subquery em vez de Count() anotado: dois M2M no mesmo JOIN multiplicam
    # as linhas (UPFs × membros) antes do DISTINCT.
    return Coalesce(
        Subquery(
            through.objects.filter(activity_id=OuterRef("pk"))
            .order_by()
            .values("activity_id")
            .annotate(total=Count("*"))
            .values("total"),
            output_field=IntegerField(),
        ),
        Value(0),
    )


def activity_export_queryset(
    *,
    user,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
    territorio_id: int | None = None,
    acao_id: int | None = None,
):
    qs = Activity.objects.select_related(
        "acao", "acao__meta",
        "municipio", "municipio__state", "municipio__territory",
        "comunidade", "tecnico_responsavel",
    ).annotate(
        _total_upfs=_contagem_m2m(Activity.upfs_participantes.through),
        _total_participantes=_contagem_m2m(Activity.membros_participantes.through),
    )
    qs = scope_queryset(
        qs,
        user,
        state_lookup="municipio__state__sigla__in",
        territory_lookup="municipio__territory__in",
        deny_message="Você não tem acesso ao módulo de Atividades do SGP.",
    )

    if periodo_inicio is not None:
        qs = qs.filter(data_inicio__date__gte=periodo_inicio)
    if periodo_fim is not None:
        qs = qs.filter(data_inicio__date__lte=periodo_fim)
    if territorio_id is not None:
        qs = qs.filter(municipio__territory_id=territorio_id)
    if acao_id is not None:
        qs = qs.filter(acao_id=acao_id)

    return qs.order_by("data_inicio", "pk")


def activity_export_rows(**kwargs) -> list[dict[str, str]]:
    agora = timezone.now()
    return [_serialize(activity, agora) for activity in activity_export_queryset(**kwargs)]


def _serialize(activity: Activity, agora) -> dict[str, str]:
    municipio = activity.municipio
    territorio = municipio.territory
    acao = activity.acao
    return {
        "id": str(activity.pk),
        "titulo": activity.titulo,
        "tipo_atividade": activity.get_tipo_atividade_display(),
        "status": activity.get_status_display(),
        "data_inicio": timezone.localtime(activity.data_inicio).strftime("%Y-%m-%d %H:%M"),
        "data_fim": timezone.localtime(activity.data_fim).strftime("%Y-%m-%d %H:%M"),
        "estado": municipio.state.sigla,
        "municipio": municipio.nome,
        "territorio": territorio.nome if territorio else "",
        "comunidade": activity.comunidade.nome if activity.comunidade_id else "",
        "meta": f"{acao.meta.numero} - {acao.meta.titulo}",
        "acao": f"{acao.numero} - {acao.descricao}",
        "tecnico_responsavel": activity.tecnico_responsavel.nome,
        "total_upfs": str(activity._total_upfs),
        "total_participantes": str(activity._total_participantes),
        "atrasada": "Sim" if activity.esta_atrasada(agora) else "Não",
    }
