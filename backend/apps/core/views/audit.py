from django_filters import rest_framework as django_filters
from rest_framework import filters, generics
from rest_framework.pagination import LimitOffsetPagination

from apps.core.models.audit_log import NOMES_DA_ENTIDADE, AuditLog
from apps.core.permissions import IsSuperAdmin
from apps.core.serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    entidade = django_filters.CharFilter(method="filter_entidade")
    timestamp_gte = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_lte = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["user", "entidade"]

    def filter_entidade(self, queryset, name, value):
        return queryset.filter(entidade__in=NOMES_DA_ENTIDADE.get(value, (value,)))


class AuditLogPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit-logs/ — listagem paginada, apenas Super Admin."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = AuditLogPagination
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AuditLogFilter
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        return AuditLog.objects.select_related("user").all()
