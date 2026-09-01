"""
Views do módulo SCA — endpoints de sync offline.

- POST /api/v1/sca/sync/push
- GET  /api/v1/sca/sync/pull
- GET  /api/v1/sca/sync/forms
- GET  /api/v1/sca/sync/status
- POST /api/v1/sca/auth/refresh
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.db.models.functions import Greatest
from django_filters import rest_framework as django_filters
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import SystemConfig, Territory
from apps.core.permissions import (
    IsAuthenticatedActiveAccess,
    IsSuperAdminOrUGPReadOnly,
)
from apps.core.services.audit import log_audit
from apps.core.services.permissions import user_has_role, user_states
from apps.core.throttling import RefreshRateThrottle
from apps.sca import services
from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sca.serializers import (
    ConflictLogDetailSerializer,
    ConflictLogListSerializer,
    ConflictResolveSerializer,
    PushBatchSerializer,
    ScaRefreshSerializer,
    SyncDeviceDetailSerializer,
    SyncDeviceListSerializer,
    SyncEventDetailSerializer,
    SyncEventListSerializer,
    TecnicoOptionSerializer,
)
from apps.sca.sync_entities import get_sync_entity

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


class SCAPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def _tipo_conexao_from_request(request) -> str | None:
    """Lê o header X-Connection-Type; valores fora das choices viram null (V1)."""
    raw = request.headers.get("X-Connection-Type", "")
    raw = raw.strip().lower()
    valid = {choice for choice, _ in SyncEvent.TipoConexao.choices}
    return raw if raw in valid else None


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

class SyncDeviceFilter(django_filters.FilterSet):
    tecnico = django_filters.NumberFilter(field_name="user_id")
    territorio = django_filters.NumberFilter(method="filter_territorio")

    class Meta:
        model = SyncDevice
        fields = ["tecnico", "territorio"]

    def filter_territorio(self, qs, name, value):
        # Semântica idêntica à de user_territories/UserListSerializer.get_territorios:
        # "dispositivos de técnicos com acesso a T". Usuário com algum perfil de
        # território específico acessa SÓ esses territórios (perfil global é ignorado);
        # sem nenhum específico, perfil global dá acesso a todos — e técnico sem
        # nenhum perfil não acessa território algum.
        from apps.core.models.user_profile import UserProfile

        tem_especifico = UserProfile.objects.filter(
            user=OuterRef("user"), territorio__isnull=False
        )
        tem_global = UserProfile.objects.filter(
            user=OuterRef("user"), territorio__isnull=True
        )
        return qs.annotate(
            tem_territorio_especifico=Exists(tem_especifico),
            tem_perfil_global=Exists(tem_global),
        ).filter(
            Q(tem_territorio_especifico=True, user__profiles__territorio_id=value)
            | Q(tem_territorio_especifico=False, tem_perfil_global=True)
        ).distinct()


class SyncEventFilter(django_filters.FilterSet):
    iniciado_em_gte = django_filters.DateTimeFilter(field_name="iniciado_em", lookup_expr="gte")
    iniciado_em_lte = django_filters.DateTimeFilter(field_name="iniciado_em", lookup_expr="lte")
    user = django_filters.NumberFilter()
    device = django_filters.NumberFilter()
    tipo = django_filters.ChoiceFilter(choices=SyncEvent.Tipo.choices)
    com_erro = django_filters.BooleanFilter(method="filter_com_erro")

    class Meta:
        model = SyncEvent
        fields = ["user", "device", "tipo", "iniciado_em_gte", "iniciado_em_lte", "com_erro"]

    def filter_com_erro(self, qs, name, value):
        if value:
            return qs.filter(contagem_erros__gt=0)
        return qs


class ConflictLogFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ConflictLog.Status.choices)
    campo_sensivel = django_filters.BooleanFilter()
    entidade = django_filters.ChoiceFilter(choices=[("upf", "UPF"), ("member", "Membro"), ("activity", "Atividade")])
    user = django_filters.NumberFilter()
    criado_em_gte = django_filters.DateTimeFilter(field_name="criado_em", lookup_expr="gte")
    criado_em_lte = django_filters.DateTimeFilter(field_name="criado_em", lookup_expr="lte")

    class Meta:
        model = ConflictLog
        fields = ["status", "campo_sensivel", "entidade", "user", "criado_em_gte", "criado_em_lte"]


# ---------------------------------------------------------------------------
# Devices (#156)
# ---------------------------------------------------------------------------

def _territorio_ids_do_usuario(user) -> list[int]:
    """Replica user_territories() usando os profiles pré-buscados (sem query).

    Perfis com território específico vencem; só-perfil-global enxerga todos
    os territórios; sem perfil territorial não enxerga nada.
    """
    especificos: list[int] = []
    tem_global = False
    for profile in user.profiles.all():
        if profile.territorio_id:
            especificos.append(profile.territorio_id)
        else:
            tem_global = True
    if especificos or not tem_global:
        return sorted(set(especificos))
    return list(Territory.objects.all().values_list("pk", flat=True))


class SyncOrderingFilter(filters.OrderingFilter):
    """Ordenação que mantém dispositivos sem sync na frente (NULLs primeiro).

    O OrderingFilter padrão do DRF reordena pelo nome do campo e perde o
    nulls_first do annotate — aqui o campo de sync é traduzido para a
    expressão equivalente antes de ordenar.
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view) or []
        if not any(o.lstrip("-") == "ultimo_sync_servidor" for o in ordering):
            return super().filter_queryset(request, queryset, view)
        traduzido = []
        for o in ordering:
            if o == "ultimo_sync_servidor":
                traduzido.append(F("ultimo_sync_servidor").asc(nulls_first=True))
            elif o == "-ultimo_sync_servidor":
                traduzido.append(F("ultimo_sync_servidor").desc(nulls_last=True))
            else:
                traduzido.append(o)
        return queryset.order_by(*traduzido)


class TecnicoListView(generics.ListAPIView):
    """GET /api/v1/sca/tecnicos/ — fonte completa (não paginada) de técnicos
    com dispositivo ou evento de sincronização, para o filtro por técnico de
    `/sca/sync-events/` (#157).

    Não reaproveita `UserViewSet?com_dispositivo=true`: aquele é paginado,
    cobre só SyncDevice (não SyncEvent — o mesmo buraco que esta issue
    corrige), exclui usuários inativos por padrão e usa uma permissão mais
    restrita (IsSuperAdmin puro, sem UGP).

    Mesma restrição territorial de BE-14/FE-12: `IsSuperAdminOrUGPReadOnly`
    já é de escopo global nas duas telas irmãs (`SyncDeviceListView`,
    `SyncEventViewSet`) — não há recorte adicional a aplicar aqui.
    """

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]
    serializer_class = TecnicoOptionSerializer
    pagination_class = None

    def get_queryset(self):
        User = get_user_model()
        # Exists (não join) evita duplicar a linha do usuário quando ele tem
        # mais de um dispositivo/evento.
        tem_dispositivo = Exists(SyncDevice.objects.filter(user_id=OuterRef("pk")))
        tem_evento = Exists(SyncEvent.objects.filter(user_id=OuterRef("pk")))
        return (
            User.objects.annotate(
                _tem_dispositivo=tem_dispositivo,
                _tem_evento=tem_evento,
            )
            .filter(Q(_tem_dispositivo=True) | Q(_tem_evento=True))
            .order_by("nome", "pk")
            .values("id", "nome", "email")
        )


class SyncDeviceListView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]
    pagination_class = SCAPagination
    serializer_class = SyncDeviceListSerializer
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, SyncOrderingFilter]
    filterset_class = SyncDeviceFilter
    search_fields = ["user__nome", "user__email"]
    ordering_fields = ["ultimo_sync_servidor", "criado_em", "nome", "device_id"]

    def _get_limiar_alerta_dias(self) -> int:
        try:
            cfg = SystemConfig.objects.filter(chave="sca_sync_alerta_dias").first()
            return int(cfg.valor) if cfg and cfg.valor else 7
        except Exception:
            return 7

    def get_queryset(self):
        return (
            SyncDevice.objects.annotate(
                ultimo_sync_servidor=Greatest("ultimo_push_em", "ultimo_pull_em"),
            )
            .select_related("user")
            .prefetch_related("user__profiles__territorio", "user__profiles__perfil")
            .order_by(F("ultimo_sync_servidor").asc(nulls_first=True))
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        limiar = self._get_limiar_alerta_dias()
        alvo = page if page is not None else list(queryset)

        usuarios = {device.user_id: device.user for device in alvo}
        territory_ids = {uid: _territorio_ids_do_usuario(u) for uid, u in usuarios.items()}

        context = self.get_serializer_context()
        context["registros_pendentes"] = services.bulk_count_pending_records(
            alvo, territory_ids
        )
        union_ids = sorted({tid for ids in territory_ids.values() for tid in ids})
        por_id = {t.pk: t for t in Territory.objects.filter(pk__in=union_ids)}
        context["territorios_por_usuario"] = {
            uid: [por_id[tid] for tid in ids if tid in por_id]
            for uid, ids in territory_ids.items()
        }
        if page is not None:
            serializer = self.get_serializer(page, many=True, context=context)
            response = self.get_paginated_response(serializer.data)
            response.data["limiar_alerta_dias"] = limiar
            return response
        serializer = self.get_serializer(queryset, many=True, context=context)
        return Response({"limiar_alerta_dias": limiar, "results": serializer.data})


# ---------------------------------------------------------------------------
# Sync Device Detail (#183 pendência)
# ---------------------------------------------------------------------------


class SyncDeviceDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]
    serializer_class = SyncDeviceDetailSerializer
    queryset = SyncDevice.objects.select_related("user").all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        territory_ids = _territorio_ids_do_usuario(instance.user)
        registros_por_entidade = services.count_pending_records_by_entity(
            instance.user, instance
        )
        from apps.core.serializers import TerritorySerializer

        territorios = list(
            Territory.objects.filter(pk__in=territory_ids)
        )
        context = {
            "registros_por_entidade": registros_por_entidade,
            "territorios_por_usuario": {instance.user_id: territorios},
        }
        serializer = self.get_serializer(instance, context=context)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Sync Events (#157)
# ---------------------------------------------------------------------------

class SyncEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]
    pagination_class = SCAPagination
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = SyncEventFilter
    ordering_fields = ["iniciado_em", "finalizado_em", "contagem", "contagem_erros"]

    def get_serializer_class(self):
        if self.action == "list":
            return SyncEventListSerializer
        return SyncEventDetailSerializer

    def get_queryset(self):
        return (
            SyncEvent.objects.all()
            .select_related("user", "device")
            .order_by(F("iniciado_em").desc(nulls_last=True), "-finalizado_em")
        )


# ---------------------------------------------------------------------------
# Conflicts (#158)
# ---------------------------------------------------------------------------

class ConflictLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = SCAPagination
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ConflictLogFilter
    ordering_fields = ["criado_em", "status", "entidade"]
    ordering = ["-criado_em"]
    _territorio_attr_path = "territorio_id"

    def get_serializer_class(self):
        if self.action == "list":
            return ConflictLogListSerializer
        return ConflictLogDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ConflictLog.objects.all().select_related("user", "device", "resolvido_por", "territorio")
        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs
        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return qs.none()
            territory_ids = [
                t.id for t in Territory.objects.all() if set(t.estados or []) & states
            ]
            return qs.filter(territorio_id__in=territory_ids)
        return qs.none()

    @action(detail=True, methods=["post"], url_path="resolver")
    def resolver(self, request, pk=None):
        conflict = self.get_object()

        if user_has_role(request.user, "articulador-estadual"):
            from apps.core.permissions import IsArticuladorEstadual
            perm = IsArticuladorEstadual()
            if not perm.has_object_permission(request, self, conflict):
                raise PermissionDenied("Você não tem permissão para resolver conflitos deste território.")
        elif not (user_has_role(request.user, "super-admin") or user_has_role(request.user, "ugp")):
            raise PermissionDenied("Permissão negada.")

        if conflict.status != ConflictLog.Status.PENDENTE:
            return Response(
                {"code": "CONFLITO_JA_RESOLVIDO", "message": "Este conflito não está mais pendente de resolução."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ConflictResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decisao = serializer.validated_data["decisao"]
        valor_manual = serializer.validated_data.get("valor_manual")

        if decisao == "local":
            valor_final = conflict.valor_local
        elif decisao == "servidor":
            valor_final = conflict.valor_servidor
        else:
            valor_final = valor_manual

        with transaction.atomic():
            entity = get_sync_entity(conflict.entidade)
            if entity:
                instance = entity.get_by_uuid_local(conflict.uuid_local)
                if instance:
                    entity.apply_changes(instance, {conflict.campo: valor_final})

            conflict.status = ConflictLog.Status.RESOLVIDO_MANUAL
            conflict.valor_final = services._jsonable(valor_final)
            conflict.resolvido_por = request.user
            conflict.resolvido_em = timezone.now()
            conflict.save()

            log_audit(
                user=request.user,
                acao="sca.conflict_resolved",
                modulo="sca",
                entidade="ConflictLog",
                entidade_id=conflict.pk,
                valores_anteriores={"status": "pendente"},
                valores_novos={
                    "status": "resolvido_manual",
                    "decisao": decisao,
                    "valor_final": services._jsonable(valor_final),
                },
                request=request,
            )

        return Response(ConflictLogDetailSerializer(conflict).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_device_id(request, body=None):
    device_id = request.headers.get("X-Device-Id") or request.query_params.get("device_id")
    if not device_id and body:
        device_id = body.get("device_id")
    return device_id


def _parse_since(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

class SyncPushView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def post(self, request):
        serializer = PushBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        device_id = _resolve_device_id(request, data)
        if not device_id and data["registros"]:
            device_id = data["registros"][0].get("device_id") or ""
        if not device_id:
            return Response(
                {"code": "DEVICE_ID_OBRIGATORIO", "message": "Informe o device_id no header X-Device-Id ou no corpo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_conexao = _tipo_conexao_from_request(request)

        device_meta = {
            "nome": request.data.get("dispositivo_nome") or request.data.get("nome") or "",
            "modelo": request.data.get("modelo") or "",
            "sistema_operacional": request.data.get("sistema_operacional") or "",
            "app_versao": request.data.get("app_versao") or "",
        }
        device = services.get_or_create_device(request.user, device_id, device_meta)
        processor = services.PushProcessor(request.user, device, device_id, tipo_conexao=tipo_conexao)
        resultados = processor.process(data["registros"])

        sucesso = sum(1 for r in resultados if r["status"] == "ok")
        return Response(
            {
                "resultados": resultados,
                "processados": len(resultados),
                "sucesso": sucesso,
                "erros": len(resultados) - sucesso,
            }
        )


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------

class SyncPullView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        since = _parse_since(request.query_params.get("since"))
        if request.query_params.get("since") and since is None:
            return Response(
                {"code": "SINCE_INVALIDO", "message": "Parâmetro 'since' inválido. Use ISO 8601 (ex: 2026-08-01T12:00:00-03:00)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device_id = _resolve_device_id(request)
        tipo_conexao = _tipo_conexao_from_request(request)
        device = services.get_or_create_device(request.user, device_id)
        payload = services.build_pull(request.user, device, since, tipo_conexao=tipo_conexao)
        return Response(payload)


# ---------------------------------------------------------------------------
# Forms (fail-safe)
# ---------------------------------------------------------------------------

class SyncFormsView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        since = _parse_since(request.query_params.get("since"))
        if request.query_params.get("since") and since is None:
            return Response(
                {"code": "SINCE_INVALIDO", "message": "Parâmetro 'since' inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        formularios = services.get_published_forms(since, user=request.user)
        return Response(
            {
                "formularios": formularios,
                "server_time": timezone.now().isoformat(),
            }
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class SyncStatusView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        device_id = _resolve_device_id(request)
        device = services.get_or_create_device(request.user, device_id)

        ultimo_sync = device.ultimo_sync_em if device else None
        pendentes = services.count_pending_records(request.user, device)

        return Response(
            {
                "ultimo_sync_servidor": ultimo_sync.isoformat() if ultimo_sync else None,
                "registros_pendentes_servidor": pendentes,
                "acesso_revogado": bool(request.user.acesso_revogado),
            }
        )


# ---------------------------------------------------------------------------
# Auth refresh do SCA
# ---------------------------------------------------------------------------

class ScaAuthRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RefreshRateThrottle]

    def post(self, request):
        serializer = ScaRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            refresh = RefreshToken(data["refresh_token"])
        except TokenError:
            security_logger.warning("sca.refresh_invalid ip=%s path=%s", request.META.get("REMOTE_ADDR"), request.path)
            return Response(
                {"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token inválido ou expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if hasattr(refresh, "check_blacklist"):
            try:
                refresh.check_blacklist()
            except TokenError:
                security_logger.warning("sca.refresh_blacklisted ip=%s path=%s", request.META.get("REMOTE_ADDR"), request.path)
                return Response(
                    {"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token inválido ou expirado."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        User = get_user_model()
        try:
            user = User.objects.get(pk=refresh["user_id"], ativo=True)
        except User.DoesNotExist:
            return Response(
                {"code": "INVALID_REFRESH_TOKEN", "message": "Usuário não encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.acesso_revogado:
            security_logger.info("sca.refresh_access_revoked user_id=%s", user.pk)
            return Response(
                {"code": "ACCESS_REVOKED", "message": "Seu acesso foi revogado. Faça novo login com internet."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        device_id = data.get("device_id") or request.headers.get("X-Device-Id")
        device = services.get_or_create_device(user, device_id)

        if services.is_session_expired(user, device):
            return Response(
                {"code": "SESSION_EXPIRED", "message": "Sessão expirada por inatividade (30 dias sem sincronização). Faça novo login."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Rotação do refresh token (mesmo comportamento do SIMPLE_JWT padrão).
        if jwt_settings.ROTATE_REFRESH_TOKENS:
            if jwt_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except (AttributeError, TokenError):
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            new_refresh = str(refresh)
        else:
            new_refresh = data["refresh_token"]

        services.register_refresh(user, device)
        security_logger.info("sca.refresh_success user_id=%s device=%s", user.pk, device_id)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": new_refresh,
            }
        )
