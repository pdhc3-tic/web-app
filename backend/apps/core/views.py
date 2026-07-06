import logging

from django.core.cache import cache
from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response

from .models import Role, State, Territory, Municipality, User, Organization
from .models.audit_log import AuditLog
from .models.notifications import Notification, _invalidate_unread_cache
from .models.system_config import SystemConfig

from .permissions import IsSuperAdmin, IsUGP, IsArticuladorEstadual

from .serializers import (
    AuditLogSerializer,
    RoleSerializer,
    StateSerializer,
    TerritorySerializer,
    MunicipalitySerializer,
    UserSerializer,
    UserListSerializer,
    UserDetailSerializer,
    NotificationSerializer,
    OrganizationSerializer,
    SystemConfigSerializer,
)

from .services.permissions import user_has_role, user_territories
from .services.audit import create_audit_log
from .throttling import NotificationUnreadCountThrottle

logger = logging.getLogger(__name__)
audit_event_logger = logging.getLogger("audit_events")


def _user_access_snapshot(user):
    return {
        "role_id": user.role_id,
        "territorios": sorted(user.territorios.values_list("pk", flat=True)),
    }

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome', 'slug']
    filterset_fields = ['ativo']

class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome', 'sigla']

class TerritoryViewSet(viewsets.ModelViewSet):
    queryset = Territory.objects.all()
    serializer_class = TerritorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome']
    filterset_fields = ['ativo', 'articulador']

class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome', 'codigo_ibge']
    filterset_fields = ['state', 'territory']

# ──────────────────────────────────────────────────────────────
# Usuários
# ──────────────────────────────────────────────────────────────

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
        logger.info("Mock: welcome email would be sent user_id=%s", user.pk)
        access_snapshot = _user_access_snapshot(user)
        if access_snapshot["role_id"] is not None or access_snapshot["territorios"]:
            create_audit_log(
                user=self.request.user,
                acao="user.access_changed",
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
        old_access = _user_access_snapshot(serializer.instance)
        user = serializer.save()
        new_access = _user_access_snapshot(user)
        if old_access != new_access:
            create_audit_log(
                user=self.request.user,
                acao="user.access_changed",
                entidade="User",
                entidade_id=user.pk,
                valores_anteriores=old_access,
                valores_novos=new_access,
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


# ──────────────────────────────────────────────────────────────
# Organizações (OSC)
# ──────────────────────────────────────────────────────────────

class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD de Organizações (OSC) com RBAC e soft-delete."""

    serializer_class = OrganizationSerializer
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nome", "cnpj"]
    filterset_fields = ["municipio__state", "territorios", "ativa", "tipo"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [(IsSuperAdmin | IsUGP | IsArticuladorEstadual)()]
        # create, partial_update, destroy → apenas SuperAdmin ou UGP
        return [(IsSuperAdmin | IsUGP)()]

    def get_queryset(self):
        user = self.request.user
        qs = Organization.objects.select_related("municipio", "municipio__state").prefetch_related("territorios")

        if user_has_role(user, "articulador-estadual"):
            territories = user_territories(user)
            qs = qs.filter(territorios__in=territories, ativa=True).distinct()
        elif self.action == "list":
            qs = qs.filter(ativa=True)

        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        territory_ids = list(instance.territorios.values_list("pk", flat=True))
        create_audit_log(
            user=self.request.user,
            acao="organization.create",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_novos={
                "organization_id": instance.pk,
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
                "territorios": territory_ids,
            },
            request=self.request,
        )
        audit_event_logger.info(
            "organization.created actor_user_id=%s organization_id=%s",
            getattr(self.request.user, "pk", None),
            instance.pk,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        old_territories = set(old.territorios.values_list("pk", flat=True))
        valores_anteriores = {
            "nome": old.nome,
            "cnpj": old.cnpj,
            "tipo": old.tipo,
            "ativa": old.ativa,
        }

        instance = serializer.save()
        new_territories = set(instance.territorios.values_list("pk", flat=True))
        
        create_audit_log(
            user=self.request.user,
            acao="UPDATE",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_anteriores=valores_anteriores,
            valores_novos={
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
            },
            request=self.request,
        )
        if old_territories != new_territories:
            create_audit_log(
                user=self.request.user,
                acao="organization.territory_change",
                entidade="Organization",
                entidade_id=instance.pk,
                valores_anteriores={
                    "territorios": sorted(old_territories),
                },
                valores_novos={
                    "territorios": sorted(new_territories),
                },
                request=self.request,
            )
        audit_event_logger.info(
            "organization.updated actor_user_id=%s organization_id=%s",
            getattr(self.request.user, "pk", None),
            instance.pk,
        )

    def perform_destroy(self, instance):
        valores_anteriores = {"nome": instance.nome, "ativa": instance.ativa}
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        create_audit_log(
            user=self.request.user,
            acao="organization.soft_delete",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_anteriores=valores_anteriores,
            valores_novos={
                "organization_id": instance.pk,
                "nome": instance.nome,
                "ativa": False,
            },
            request=self.request,
        )
        audit_event_logger.info(
            "organization.soft_deleted actor_user_id=%s organization_id=%s",
            getattr(self.request.user, "pk", None),
            instance.pk,
        )


# ──────────────────────────────────────────────────────────────
# Notificações
# ──────────────────────────────────────────────────────────────

class NotificationPagination(LimitOffsetPagination):
    default_limit = 20


class NotificationListView(generics.ListAPIView):
    """GET /api/v1/notifications/me/ — notificações do usuário autenticado."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    ordering = ["-enviado_em"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-enviado_em")


class NotificationMarkReadView(generics.UpdateAPIView):
    """PATCH /api/v1/notifications/{id}/read/ — marca como lida."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        # Filtra por user — se a notificação não pertence ao user, retorna 404 (não 403)
        return Notification.objects.filter(user=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        notification = self.get_object()

        if notification.lido_em is None:
            notification.lido_em = timezone.now()
            notification.save(update_fields=["lido_em"])
            _invalidate_unread_cache(request.user.pk)

        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """POST /api/v1/notifications/mark-all-read/ — marca todas como lidas."""
    updated_count = Notification.objects.filter(
        user=request.user,
        lido_em__isnull=True,
    ).update(lido_em=timezone.now())

    if updated_count > 0:
        _invalidate_unread_cache(request.user.pk)
        logger.info(
            "notifications.mark_all_read user_id=%s updated_count=%s",
            request.user.pk,
            updated_count,
        )

    return Response({"updated_count": updated_count}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([NotificationUnreadCountThrottle])
def unread_count(request):
    """GET /api/v1/notifications/me/unread-count/ — contagem de não-lidas com cache 30s."""
    cache_key = f"notification_unread_count_{request.user.pk}"
    count = cache.get(cache_key)

    if count is None:
        count = Notification.objects.filter(
            user=request.user,
            lido_em__isnull=True,
        ).count()
        cache.set(cache_key, count, timeout=30)

    return Response({"count": count}, status=status.HTTP_200_OK)

class AuditLogFilter(django_filters.FilterSet):
    timestamp_gte = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_lte = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["user", "entidade"]


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
        audit_event_logger.info(
            "audit_log.accessed actor_user_id=%s path=%s",
            getattr(self.request.user, "pk", None),
            self.request.path,
        )
        return AuditLog.objects.select_related("user").all()

# ──────────────────────────────────────────────────────────────
# System Config
# ──────────────────────────────────────────────────────────────


class IsSuperAdminOrUGPReadOnly(IsSuperAdmin):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return user_has_role(request.user, "super-admin") or user_has_role(request.user, "ugp")
        return super().has_permission(request, view)


class SystemConfigListView(generics.ListAPIView):
    """GET /api/v1/system-config/ — lista configurações do sistema."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [IsAuthenticated, IsSuperAdminOrUGPReadOnly]


class SystemConfigDetailView(generics.RetrieveUpdateAPIView):
    """GET|PATCH /api/v1/system-config/{chave}/ — detalhe ou atualização."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    lookup_field = "chave"
    http_method_names = ["get", "patch"]
    permission_classes = [IsAuthenticated, IsSuperAdminOrUGPReadOnly]

    def perform_update(self, serializer):
        instance = serializer.save(atualizado_por=self.request.user)
        audit_event_logger.info(
            "system_config.updated actor_user_id=%s chave=%s",
            getattr(self.request.user, "pk", None),
            instance.chave,
        )
