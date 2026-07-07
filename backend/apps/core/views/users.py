import logging

from django_filters import rest_framework as django_filters
from rest_framework import filters, status, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from apps.core.models import User
from apps.core.permissions import IsSuperAdmin
from apps.core.serializers import UserDetailSerializer, UserListSerializer


logger = logging.getLogger(__name__)


class UserFilter(django_filters.FilterSet):
    perfil = django_filters.NumberFilter(field_name="role_id")
    territorio = django_filters.NumberFilter(field_name="territorios__id")
    ativo = django_filters.BooleanFilter()
    ultimo_login_gte = django_filters.DateTimeFilter(
        field_name="ultimo_login", lookup_expr="gte"
    )
    ultimo_login_lte = django_filters.DateTimeFilter(
        field_name="ultimo_login", lookup_expr="lte"
    )

    class Meta:
        model = User
        fields = [
            "perfil", "territorio", "ativo",
            "ultimo_login_gte", "ultimo_login_lte",
        ]


class UserPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsSuperAdmin]
    pagination_class = UserPagination
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = UserFilter
    search_fields = ["nome", "email"]
    ordering_fields = ["ultimo_login", "nome", "email"]
    ordering = ["-ultimo_login"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return UserListSerializer
        return UserDetailSerializer

    def get_queryset(self):
        qs = User.objects.all()
        if "ativo" not in self.request.query_params:
            qs = qs.filter(ativo=True)
        return qs.select_related("role").prefetch_related("territorios")

    def perform_create(self, serializer):
        user = serializer.save()
        logger.info(
            "Mock: welcome email would be sent to %s (user_id=%s)",
            user.email, user.pk,
        )

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.ativo = False
        instance.save(update_fields=["ativo"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
