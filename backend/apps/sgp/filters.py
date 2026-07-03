import re

import django_filters
from django.db.models import Q

from apps.sgp.models import UPF


class UPFFilter(django_filters.FilterSet):
    municipio = django_filters.NumberFilter(field_name="municipio_id")
    territorio = django_filters.NumberFilter(field_name="territorio_id")
    projeto = django_filters.NumberFilter(field_name="projeto_id")
    ativa = django_filters.BooleanFilter()
    criado_em__gte = django_filters.DateTimeFilter(
        field_name="criado_em", lookup_expr="gte"
    )
    criado_em__lte = django_filters.DateTimeFilter(
        field_name="criado_em", lookup_expr="lte"
    )
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = UPF
        fields = [
            "municipio",
            "territorio",
            "projeto",
            "ativa",
            "criado_em__gte",
            "criado_em__lte",
            "q",
        ]

    def filter_q(self, queryset, name, value):
        q = Q(nome_titular__icontains=value)
        digits_only = re.sub(r"\D", "", value)
        if digits_only:
            q |= Q(cpf__startswith=digits_only)
        return queryset.filter(q)
