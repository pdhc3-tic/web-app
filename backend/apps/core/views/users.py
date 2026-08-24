import logging
from datetime import datetime, timezone as dt_timezone

from django.db.models import Count, Max, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.models import User
from apps.core.permissions import IsSuperAdmin
from apps.core.serializers import UserDetailSerializer, UserListSerializer
from apps.core.services.audit import log_audit


logger = logging.getLogger(__name__)
audit_event_logger = logging.getLogger("audit_events")

_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def _user_access_snapshot(user):
    from apps.core.models.user_profile import UserProfile
    profiles = UserProfile.objects.filter(user=user).values("perfil_id", "territorio_id")
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
    com_dispositivo = django_filters.BooleanFilter(method="filter_com_dispositivo")

    class Meta:
        model = User
        fields = [
            "perfil", "territorio", "ativo",
            "ultimo_login_gte", "ultimo_login_lte",
            "com_dispositivo",
        ]

    def filter_com_dispositivo(self, qs, name, value):
        if value:
            return qs.filter(sca_devices__isnull=False).distinct()
        return qs


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
        if self._com_dispositivo_ativo():
            qs = qs.annotate(
                qtd_dispositivos=Count("sca_devices", distinct=True),
                ultimo_sync_dispositivos=Max(
                    Greatest(
                        Coalesce("sca_devices__ultimo_push_em", Value(_EPOCH)),
                        Coalesce("sca_devices__ultimo_pull_em", Value(_EPOCH)),
                    )
                ),
            )
        return qs.prefetch_related("profiles__perfil", "profiles__territorio")

    def _com_dispositivo_ativo(self) -> bool:
        return self.request.query_params.get("com_dispositivo", "").lower() in ("true", "1")

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
            "user.created user_id=%s target_user_id=%s",
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
            "user.updated user_id=%s target_user_id=%s",
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

    # ------------------------------------------------------------------
    # Acesso do SCA — revogar / reativar
    # ------------------------------------------------------------------
    def _invalidate_all_sessions(self, user):
        """Blacklista todos os refresh tokens ativos do usuário (todos os dispositivos)."""
        tokens = OutstandingToken.objects.filter(user=user)
        revoked = 0
        for token in tokens:
            _, created = BlacklistedToken.objects.get_or_create(token=token)
            revoked += int(created)
        return revoked

    @action(detail=True, methods=["patch"], url_path="revogar-acesso")
    def revogar_acesso(self, request, pk=None):
        instance = self.get_object()
        instance.acesso_revogado = True
        instance.acesso_revogado_em = timezone.now()
        instance.acesso_revogado_por = request.user
        instance.save(update_fields=[
            "acesso_revogado",
            "acesso_revogado_em",
            "acesso_revogado_por",
        ])
        revoked = self._invalidate_all_sessions(instance)
        log_audit(
            user=request.user,
            acao="user.access_revoked",
            modulo="core",
            entidade="User",
            entidade_id=instance.pk,
            valores_anteriores={"acesso_revogado": False},
            valores_novos={
                "acesso_revogado": True,
                "sessoes_invalidadas": revoked,
            },
            request=request,
        )
        audit_event_logger.info(
            "user.access_revoked actor_user_id=%s target_user_id=%s sessions=%s",
            getattr(request.user, "pk", None),
            instance.pk,
            revoked,
        )
        return Response(
            {
                "message": "Acesso revogado. O app SCA fará o wipe remoto no próximo sync.",
                "acesso_revogado": True,
                "sessoes_invalidadas": revoked,
            }
        )

    @action(detail=True, methods=["patch"], url_path="reativar-acesso")
    def reativar_acesso(self, request, pk=None):
        instance = self.get_object()
        instance.acesso_revogado = False
        instance.acesso_revogado_em = None
        instance.acesso_revogado_por = None
        instance.save(update_fields=[
            "acesso_revogado",
            "acesso_revogado_em",
            "acesso_revogado_por",
        ])
        revoked = self._invalidate_all_sessions(instance)
        log_audit(
            user=request.user,
            acao="user.access_reactivated",
            modulo="core",
            entidade="User",
            entidade_id=instance.pk,
            valores_anteriores={"acesso_revogado": True},
            valores_novos={"acesso_revogado": False},
            request=request,
        )
        audit_event_logger.info(
            "user.access_reactivated actor_user_id=%s target_user_id=%s",
            getattr(request.user, "pk", None),
            instance.pk,
        )
        return Response(
            {
                "message": "Acesso reativado. O técnico precisa fazer um novo login (sessões antigas invalidadas).",
                "acesso_revogado": False,
                "sessoes_invalidadas": revoked,
            }
        )
