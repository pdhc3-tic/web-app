import django_filters
from django.db.models import Q

from apps.sgp.models import Indicator, WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta


class WorkPlanMetaFilter(django_filters.FilterSet):
    numero = django_filters.NumberFilter()
    data_inicio__gte = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="gte"
    )
    data_inicio__lte = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="lte"
    )
    data_fim__gte = django_filters.DateFilter(
        field_name="data_fim", lookup_expr="gte"
    )
    data_fim__lte = django_filters.DateFilter(
        field_name="data_fim", lookup_expr="lte"
    )

    class Meta:
        model = WorkPlanMeta
        fields = [
            "numero",
            "data_inicio__gte",
            "data_inicio__lte",
            "data_fim__gte",
            "data_fim__lte",
        ]


class WorkPlanAcaoFilter(django_filters.FilterSet):
    meta = django_filters.NumberFilter(field_name="meta_id")
    submeta = django_filters.NumberFilter(field_name="submeta_id")
    indicador = django_filters.NumberFilter(field_name="indicador_id")
    data_inicio__gte = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="gte"
    )
    data_inicio__lte = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="lte"
    )
    data_fim__gte = django_filters.DateFilter(
        field_name="data_fim", lookup_expr="gte"
    )
    data_fim__lte = django_filters.DateFilter(
        field_name="data_fim", lookup_expr="lte"
    )

    class Meta:
        model = WorkPlanAcao
        fields = [
            "meta",
            "submeta",
            "indicador",
            "data_inicio__gte",
            "data_inicio__lte",
            "data_fim__gte",
            "data_fim__lte",
        ]


class WorkPlanSubmetaFilter(django_filters.FilterSet):
    meta = django_filters.NumberFilter(field_name="meta_id")

    class Meta:
        model = WorkPlanSubmeta
        fields = ["meta"]


class IndicatorFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Indicator
        fields = ["ativo", "categoria", "forma_apuracao", "unidade_medida", "q"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(codigo__icontains=value) | Q(nome__icontains=value))
