import django_filters

from apps.sgp.models import WorkPlanAcao, WorkPlanMeta


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
            "data_inicio__gte",
            "data_inicio__lte",
            "data_fim__gte",
            "data_fim__lte",
        ]
