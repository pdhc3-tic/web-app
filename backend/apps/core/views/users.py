import logging

from django_filters import rest_framework as django_filters
from rest_framework import filters, status, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from apps.core.models import User
from apps.core.permissions import IsSuperAdmin
from apps.core.serializers import UserDetailSerializer, UserListSerializer
from apps.core.services.audit import log_audit


logger = logging.getLogger(__name__)
audit_event_logger = logging.getLogger("audit_events")


def _user_access_snapshot(user):
    profiles = user.profiles.all().values("perfil_id", "territorio_id")
    return {
        "perfis": [
            {"perfil_id": p["perfil_id"], "territorio_id": p["territorio_id"]}
            for p in profiles
        ],
    }


class UserFilter(django_filters.FilterSet):
    perfil = django_filters.NumberFilter(field_name="profiles__perfil_id")
    territorio = django_filters.NumberFilter(field_name="profiles__territorio_id")
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
        return qs.prefetch_related("profiles__perfil", "profiles__territorio")

    def perform_create(self, serializer):
        user = serializer.save()
        logger.info("Mock: welcome email would be sent user_id=%s", user.pk)
        access_snapshot = _user_access_snapshot(user)
        if access_snapshot["perfis"]:
            log_audit(
                user=self.request.user,
                acao="user.access_changed",
                modulo="core",
                entidade="User",
                entidade_id=user.pk,
                valores_anteriores={},
                valores_novos=access_snapshot,
                request=self.request,
            )
        audit_event_logger.info(
            "user.created actor_user_id=%s target_user_id=%s",
            getattr(self.request.user, "pk", None),
            user.pk,
        )

    def perform_update(self, serializer):
        old_snapshot = _user_access_snapshot(serializer.instance)
        user = serializer.save()
        new_snapshot = _user_access_snapshot(user)
        if old_snapshot != new_snapshot:
            log_audit(
                user=self.request.user,
                acao="user.access_changed",
                modulo="core",
                entidade="User",
                entidade_id=user.pk,
                valores_anteriores=old_snapshot,
                valores_novos=new_snapshot,
                request=self.request,
            )
        audit_event_logger.info(
            "user.updated actor_user_id=%s target_user_id=%s",
            getattr(self.request.user, "pk", None),
            user.pk,
        )

    def perform_destroy(self, instance):
        instance.ativo = False
        instance.save(update_fields=["ativo"])
        audit_event_logger.info(
            "user.deactivated actor_user_id=%s target_user_id=%s",
            getattr(self.request.user, "pk", None),
            instance.pk,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
