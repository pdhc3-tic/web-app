from rest_framework import viewsets, filters, generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from .models import Role, State, Territory, Municipality, Organization
from .models.audit_log import AuditLog
from .models.notifications import Notification, _invalidate_unread_cache
from .permissions import IsSuperAdmin, IsUGP, IsArticuladorEstadual
from .serializers import (
    RoleSerializer, StateSerializer, TerritorySerializer,
    MunicipalitySerializer, UserSerializer, NotificationSerializer,
    OrganizationSerializer,
)
from .services.permissions import user_has_role, user_territories
from .throttling import NotificationUnreadCountThrottle

User = get_user_model()

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
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
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nome']
    filterset_fields = ['ativo', 'articulador']

class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nome', 'codigo_ibge']
    filterset_fields = ['state', 'territory']

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nome', 'email']
    filterset_fields = ['role', 'ativo']


# ──────────────────────────────────────────────────────────────
# Organizações (OSC)
# ──────────────────────────────────────────────────────────────

class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD de Organizações (OSC) com RBAC e soft-delete."""

    serializer_class = OrganizationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
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
        AuditLog.objects.create(
            user=self.request.user,
            acao="CREATE",
            modulo="core",
            entidade="Organization",
            entidade_id=str(instance.pk),
            valores_anteriores={},
            valores_novos={
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "nome": old.nome,
            "cnpj": old.cnpj,
            "tipo": old.tipo,
            "ativa": old.ativa,
        }

        instance = serializer.save()
        
        AuditLog.objects.create(
            user=self.request.user,
            acao="UPDATE",
            modulo="core",
            entidade="Organization",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_destroy(self, instance):
        valores_anteriores = {"nome": instance.nome, "ativa": instance.ativa}
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        AuditLog.objects.create(
            user=self.request.user,
            acao="DESTROY",
            modulo="core",
            entidade="Organization",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={"ativa": False},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
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
