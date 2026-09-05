import csv
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.apps import apps
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.views import APIView
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from rest_framework.pagination import LimitOffsetPagination
from apps.core.permissions import IsAuthenticatedActiveAccess
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP
from apps.core.services.membro_audit import log_membro_change, sensitive_fields_changed
from apps.core.services.permissions import (
    user_has_role, user_role_slugs, user_states, user_territories
)
from apps.core.utils import get_config
from apps.sgp.cache import UPF_MAP_CACHE_TIMEOUT, build_upf_map_cache_key
from apps.sgp.constants import (
    AGUA_CHOICES,
    COR_RACA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    ESCOLARIDADE_CHOICES,
    GENERO_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    PARENTESCO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SAUDE_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)
from apps.core.models.territory import Territory
from apps.sgp.filters import ActivityFilter, TecnicoFilter, UPFFilter
from apps.sgp.models import (
    Activity, ActivityDocument, ActivityPhoto, Comunidade, Cultura, EspecieAnimal,
    MembroFamilia, Tecnico, UPF, Projeto
)
from apps.sgp.services.membro_export import (
    MEMBROS_EXPORT_UPF_LIMIT,
    ExportLimitExceeded,
    membro_export_rows_for_scope,
    membro_export_rows_for_upf,
)


UPF_ACCESS_ROLES = ("super-admin", "ugp", "articulador-estadual", "adt-acr")


def upfs_acessiveis_ao_usuario(user, role_slugs=None):
    """Retorna queryset de UPFs acessíveis ao usuário conforme regras territoriais.

    `role_slugs` pode ser passado já computado (ver `UPFViewSet.get_queryset`)
    para evitar refazer a checagem de roles do usuário em outra query.
    """
    qs = UPF.objects.all()
    if role_slugs is None:
        role_slugs = user_role_slugs(user, UPF_ACCESS_ROLES)
    if "super-admin" in role_slugs or "ugp" in role_slugs:
        return qs
    if "articulador-estadual" in role_slugs:
        states = user_states(user)
        if not states:
            return qs.none()
        return qs.filter(municipio__state__sigla__in=states)
    if "adt-acr" in role_slugs:
        territories = user_territories(user)
        if not territories.exists():
            return qs.none()
        return qs.filter(territorio__in=territories)
    return qs.none()


def tecnicos_acessiveis_ao_usuario(user):
    """Retorna queryset de Tecnicos acessíveis ao usuário conforme regras territoriais."""
    qs = Tecnico.objects.all()
    if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
        return qs
    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        if not states:
            return qs.none()
        territorio_ids = [
            t.pk for t in Territory.objects.all() if set(t.estados or []) & states
        ]
        return qs.filter(territorio_id__in=territorio_ids)
    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        if not territories.exists():
            return qs.none()
        return qs.filter(territorio__in=territories)
    return qs.none()


def data_limite_aniversario(hoje, anos):
    """Data mínima para quem ainda não completou `anos` anos hoje.

    Corresponde ao aniversário de `anos` anos atrás: quem nasceu nesta data
    ou depois ainda não completou `anos` anos. Em anos não bissextos, um
    aniversário que cairia em 29/fev é tratado como 28/fev.
    """
    try:
        return date(hoje.year - anos, hoje.month, hoje.day)
    except ValueError:
        return date(hoje.year - anos, hoje.month, 28)


from apps.sgp.pagination import (
    ActivityPagination, CatalogoPagination, HistoricoPagination, UPFPagination
)
from apps.sgp.serializers import (
    ActivityCalendarioSerializer,
    ActivityDetailSerializer,
    ActivityListSerializer,
    ComunidadeSerializer,
    CulturaSerializer,
    EspecieAnimalSerializer,
    HistoricoEntrySerializer,
    MembroDetailSerializer,
    MembroExportQuerySerializer,
    MembroListSerializer,
    MunicipioNestedSerializer,
    ProjetoSerializer,
    TecnicoSerializer,
    UPFDetailSerializer,
    UPFListSerializer,
)
from .upf_foto import UPFPhotoMixin
from .upf_documentos import UPFDocumentViewSet
from .activity_foto import ActivityPhotoMixin
from .activity_documentos import ActivityDocumentMixin
from .production import ProductionViewSet
from apps.sgp.tasks import sync_activity_to_google_calendar

logger = logging.getLogger("apps.sgp.views")


class QSearchFilter(filters.SearchFilter):
    search_param = 'q'


class CatalogoListView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = CatalogoPagination
    http_method_names = ["get", "head", "options"]
    model = None

    def get_queryset(self):
        qs = self.model.objects.all()

        ativa_param = self.request.query_params.get("ativa", "").lower()
        is_admin = user_has_role(self.request.user, "super-admin") or user_has_role(
            self.request.user, "ugp"
        )
        if ativa_param != "false" or not is_admin:
            qs = qs.filter(ativa=True)

        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(nome__icontains=q)

        categoria = self.request.query_params.get("categoria", "").strip()
        if categoria:
            qs = qs.filter(categoria=categoria)

        return qs


class CulturaListView(CatalogoListView):
    serializer_class = CulturaSerializer
    model = Cultura


class EspecieAnimalListView(CatalogoListView):
    serializer_class = EspecieAnimalSerializer
    model = EspecieAnimal


class ComunidadePagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


# Documentação OpenAPI da action UPFViewSet.mapa — o payload real é montado
# em _build_mapa_feature. Desvio entre os dois é pego por
# test_mapa_openapi_schema_tipa_municipio_estado.
class _UPFMapGeometrySerializer(serializers.Serializer):
    type = serializers.CharField(default="Point")
    coordinates = serializers.ListField(child=serializers.FloatField())


class _UPFMapPropertiesSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome_titular = serializers.CharField()
    municipio = MunicipioNestedSerializer()
    territorio = serializers.CharField()
    ativa = serializers.BooleanField()


class _UPFMapFeatureSerializer(serializers.Serializer):
    type = serializers.CharField(default="Feature")
    geometry = _UPFMapGeometrySerializer()
    properties = _UPFMapPropertiesSerializer()


class UPFViewSet(UPFPhotoMixin, viewsets.ModelViewSet):
    MAPA_FEATURE_LIMIT = 10000
    queryset = UPF.objects.select_related(
        "municipio", "municipio__state", "territorio", "projeto", "criado_por"
    ).all()
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = UPFFilter
    ordering_fields = ["criado_em", "titular__nome_completo"]
    ordering = ["-criado_em"]

    def get_serializer_class(self):
        if self.action == "list":
            return UPFListSerializer
        if self.action == "historico":
            return HistoricoEntrySerializer
        return UPFDetailSerializer

    def filter_queryset(self, queryset):
        if "ativa" not in self.request.query_params:
            queryset = queryset.filter(ativa=True)
        return super().filter_queryset(queryset)

    def get_queryset(self):
        qs = UPF.objects.select_related(
            "municipio", "municipio__state", "territorio", "projeto",
            "criado_por", "titular",
        ).prefetch_related("membros").all()

        user = self.request.user
        role_slugs = user_role_slugs(user, UPF_ACCESS_ROLES)
        if not role_slugs:
            raise PermissionDenied("Você não tem acesso ao módulo SGP.")

        pks = upfs_acessiveis_ao_usuario(user, role_slugs=role_slugs).values_list("pk", flat=True)
        return qs.filter(pk__in=pks)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="bbox",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Bounding box no formato lng_sw,lat_sw,lng_ne,lat_ne.",
            ),
            OpenApiParameter("municipio", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("territorio", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("projeto", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("ativa", OpenApiTypes.BOOL, OpenApiParameter.QUERY),
        ],
        responses={
            200: inline_serializer(
                name="UPFMapFeatureCollection",
                fields={
                    "type": serializers.CharField(default="FeatureCollection"),
                    "features": _UPFMapFeatureSerializer(many=True),
                    "truncated": serializers.BooleanField(),
                    "message": serializers.CharField(required=False),
                },
            )
        },
        description=(
            "Retorna UPFs georreferenciadas em GeoJSON FeatureCollection. "
            "Cada feature possui geometry.coordinates na ordem [lng, lat] "
            "e properties mínimo: id, nome_titular, municipio, territorio e ativa."
        ),
    )
    @action(detail=False, methods=["get"], url_path="mapa")
    def mapa(self, request):
        bbox = self._parse_bbox(request.query_params.get("bbox"))
        cache_key = build_upf_map_cache_key(
            request.user.pk,
            request.query_params,
        )
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        )
        if bbox is not None:
            lng_sw, lat_sw, lng_ne, lat_ne = bbox
            queryset = queryset.filter(
                longitude__gte=lng_sw,
                longitude__lte=lng_ne,
                latitude__gte=lat_sw,
                latitude__lte=lat_ne,
            )

        queryset = (
            queryset.select_related(None)
            .prefetch_related(None)
            .select_related("titular", "municipio", "municipio__state", "territorio")
            .only(
                "id",
                "titular",
                "titular__nome_completo",
                "latitude",
                "longitude",
                "municipio",
                "municipio__nome",
                "municipio__state",
                "municipio__state__sigla",
                "municipio__state__nome",
                "territorio",
                "territorio__nome",
                "ativa",
            )
            .order_by("id")
        )

        upfs = list(queryset[: self.MAPA_FEATURE_LIMIT + 1])
        truncated = len(upfs) > self.MAPA_FEATURE_LIMIT
        upfs = upfs[: self.MAPA_FEATURE_LIMIT]

        response_data = {
            "type": "FeatureCollection",
            "features": [self._build_mapa_feature(upf) for upf in upfs],
            "truncated": truncated,
        }
        if truncated:
            response_data["message"] = (
                "Resultado limitado a 10000 UPFs. Use o filtro bbox para reduzir a área."
            )

        cache.set(cache_key, response_data, UPF_MAP_CACHE_TIMEOUT)
        return Response(response_data)

    def _parse_bbox(self, value):
        if not value:
            return None

        parts = value.split(",")
        if len(parts) != 4:
            raise serializers.ValidationError(
                {"bbox": "Use o formato lng_sw,lat_sw,lng_ne,lat_ne."}
            )

        try:
            lng_sw, lat_sw, lng_ne, lat_ne = [Decimal(part.strip()) for part in parts]
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError(
                {
                    "bbox": (
                        "Use valores numéricos no formato "
                        "lng_sw,lat_sw,lng_ne,lat_ne."
                    )
                }
            )

        if lng_sw > lng_ne or lat_sw > lat_ne:
            raise serializers.ValidationError(
                {"bbox": "O sudoeste do bbox deve vir antes do nordeste."}
            )

        return lng_sw, lat_sw, lng_ne, lat_ne

    def _build_mapa_feature(self, upf):
        # Dict puro (não usa _UPFMapFeatureSerializer) para evitar overhead
        # de Serializer por item em listas de até MAPA_FEATURE_LIMIT UPFs.
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(upf.longitude), float(upf.latitude)],
            },
            "properties": {
                "id": upf.pk,
                "nome_titular": upf.titular.nome_completo,
                "municipio": MunicipioNestedSerializer(upf.municipio).data,
                "territorio": upf.territorio.nome,
                "ativa": upf.ativa,
            },
        }

    @action(detail=True, methods=["get"], url_path="historico")
    def historico(self, request, pk=None):
        upf = self.get_object()
        q = Q(entidade="UPF", entidade_id=str(upf.pk))

        incluir_membros = request.query_params.get("incluir_membros") == "true"
        if incluir_membros:
            MembroFamilia = apps.get_model("sgp", "MembroFamilia")
            if MembroFamilia is not None:
                member_ids = list(
                    MembroFamilia.objects.filter(upf_id=upf.pk).values_list(
                        "pk", flat=True
                    )
                )
                if member_ids:
                    q |= Q(
                        entidade="MembroFamilia",
                        entidade_id__in=[str(m) for m in member_ids],
                    )

        usuario_filter = request.query_params.get("usuario")
        if usuario_filter:
            q &= Q(user_id=usuario_filter)

        desde = request.query_params.get("desde")
        if desde:
            try:
                dt = datetime.fromisoformat(desde)
                q &= Q(timestamp__gte=dt)
            except (ValueError, TypeError):
                pass

        ate = request.query_params.get("ate")
        if ate:
            try:
                dt = datetime.fromisoformat(ate)
                q &= Q(timestamp__lte=dt)
            except (ValueError, TypeError):
                pass

        logs = (
            AuditLog.objects.filter(q)
            .select_related("user")
            .order_by("-timestamp")
        )

        entries = []
        for log in logs:
            if log.acao.lower().endswith(".create"):
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=None, valor_novo=log.valores_novos)
                )
            elif log.acao.lower().endswith(".update"):
                old = log.valores_anteriores or {}
                new = log.valores_novos or {}
                all_keys = set(old.keys()) | set(new.keys())
                for key in sorted(all_keys):
                    old_val = old.get(key)
                    new_val = new.get(key)
                    if old_val != new_val:
                        entries.append(
                            self._build_entry(log, campo=key, valor_anterior=old_val, valor_novo=new_val, suffix=key)
                        )
            else:
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=log.valores_anteriores, valor_novo=log.valores_novos)
                )

        campo_filter = request.query_params.get("campo")
        if campo_filter:
            entries = [e for e in entries if e["campo"] == campo_filter]

        paginator = HistoricoPagination()
        page = paginator.paginate_queryset(entries, request)
        serializer = HistoricoEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def _build_entry(self, log, campo, valor_anterior, valor_novo, suffix=None):
        eid = str(log.pk) if suffix is None else f"{log.pk}_{suffix}"
        return {
            "id": eid,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "usuario_id": log.user.pk if log.user else None,
            "usuario_nome": log.user.nome if log.user else None,
            "timestamp": log.timestamp,
        }

    def _log_audit(self, acao, instance, valores_anteriores=None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="UPF",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos={
                "upf_id": instance.pk,
                "nome_titular": instance.titular.nome_completo,
                "cpf": instance.titular.cpf,
                "projeto_id": instance.projeto_id,
                "municipio_id": instance.municipio_id,
                "territorio_id": instance.territorio_id,
                "comunidade_id": instance.comunidade_id,
                "ativa": instance.ativa,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_create(self, serializer):
        instance = serializer.save(criado_por=self.request.user, ultima_origem="web")
        self._log_audit("UPF.create", instance)
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.create",
            membro=instance.titular,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                None, {"cor_raca": instance.titular.cor_raca}
            ),
            request=self.request,
            extra_novos={"via": "upf.titular"},
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "upf_id": old.pk,
            "nome_titular": old.titular.nome_completo,
            "cpf": old.titular.cpf,
            "projeto_id": old.projeto_id,
            "municipio_id": old.municipio_id,
            "territorio_id": old.territorio_id,
            "comunidade_id": old.comunidade_id,
            "ativa": old.ativa,
        }
        anteriores_sensiveis = {"cor_raca": old.titular.cor_raca}
        instance = serializer.save(ultima_origem="web")
        self._log_audit("UPF.update", instance, valores_anteriores)
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.update",
            membro=instance.titular,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                anteriores_sensiveis, {"cor_raca": instance.titular.cor_raca}
            ),
            request=self.request,
            extra_novos={"via": "upf.titular"},
        )

    def perform_destroy(self, instance):
        valores_anteriores = {
            "upf_id": instance.pk,
            "nome_titular": instance.titular.nome_completo,
            "cpf": instance.titular.cpf,
            "projeto_id": instance.projeto_id,
            "municipio_id": instance.municipio_id,
            "territorio_id": instance.territorio_id,
            "comunidade_id": instance.comunidade_id,
            "ativa": instance.ativa,
        }
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        self._log_audit("UPF.deactivate", instance, valores_anteriores)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ComunidadeViewSet(viewsets.ModelViewSet):
    queryset = Comunidade.objects.all()
    serializer_class = ComunidadeSerializer
    pagination_class = ComunidadePagination
    filter_backends = [QSearchFilter]
    search_fields = ['nome']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        qs = Comunidade.objects.select_related(
            'municipio', 'municipio__state', 'criada_por',
        )

        municipio_id = self.kwargs.get('municipio_id')
        if municipio_id is not None:
            qs = qs.filter(municipio_id=municipio_id)

        ativa_param = self.request.query_params.get('ativa')
        if ativa_param is not None and ativa_param.lower() == 'false':
            user = self.request.user
            if (
                user.is_authenticated
                and (user_has_role(user, "super-admin") or user_has_role(user, "ugp"))
            ):
                return qs.filter(ativa=False)
        return qs.filter(ativa=True)

    def list(self, request, *args, **kwargs):
        if 'municipio_id' not in self.kwargs:
            return Response(
                {'detail': 'Listagem global não disponível. Use /api/v1/municipios/{id}/comunidades/.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if 'municipio_id' not in self.kwargs:
            return Response(
                {'detail': 'Criação global não disponível. Use /api/v1/municipios/{id}/comunidades/.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().create(request, *args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        municipio_id = self.kwargs.get('municipio_id')
        if municipio_id is not None and self.action == 'create':
            data = kwargs.get('data')
            if data is not None:
                data = data.copy()
                data['municipio'] = int(municipio_id)
                kwargs['data'] = data
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        try:
            instance = serializer.save(criada_por=self.request.user, ativa=True)
        except (IntegrityError, DjangoValidationError):
            raise serializers.ValidationError({
                'nome': 'Já existe uma comunidade ativa com este nome neste município.',
            })
        AuditLog.objects.create(
            user=self.request.user,
            acao='comunidade.create',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_novos={
                'id': instance.pk,
                'nome': instance.nome,
                'municipio_id': instance.municipio_id,
                'ativa': instance.ativa,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            'nome': old.nome,
            'municipio_id': old.municipio_id,
            'lat': str(old.lat) if old.lat else None,
            'lng': str(old.lng) if old.lng else None,
            'ativa': old.ativa,
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao='UPDATE',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                'nome': instance.nome,
                'municipio_id': instance.municipio_id,
                'lat': str(instance.lat) if instance.lat else None,
                'lng': str(instance.lng) if instance.lng else None,
                'ativa': instance.ativa,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

    def perform_destroy(self, instance):
        valores_anteriores = {'nome': instance.nome, 'ativa': instance.ativa}
        instance.ativa = False
        instance.save(update_fields=['ativa'])
        AuditLog.objects.create(
            user=self.request.user,
            acao='comunidade.soft_delete',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_novos={
                'id': instance.pk,
                'nome': instance.nome,
                'ativa': False,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TecnicoViewSet(viewsets.ModelViewSet):
    serializer_class = TecnicoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TecnicoFilter
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        user = self.request.user
        if not (
            user_has_role(user, "super-admin")
            or user_has_role(user, "ugp")
            or user_has_role(user, "articulador-estadual")
            or user_has_role(user, "adt-acr")
        ):
            raise PermissionDenied("Você não tem acesso ao módulo de Técnicos do SGP.")
        return tecnicos_acessiveis_ao_usuario(user).select_related("user", "territorio", "osc")

    def perform_destroy(self, instance):
        """Soft-delete via ativo=False. Não afeta Activity.tecnico_responsavel (FK direta a User)."""
        instance.ativo = False
        instance.save(update_fields=["ativo"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _membros_csv_response(columns, rows, filename):
    """CSV UTF-8 com BOM, no mesmo formato de `WorkPlanExportView` (docs/export.md)."""
    content = StringIO()
    writer = csv.writer(content)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in columns])
    response = HttpResponse(
        "\ufeff" + content.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class MembroViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_upf(self):
        upf_pk = self.kwargs["upf_pk"]
        return get_object_or_404(upfs_acessiveis_ao_usuario(self.request.user), pk=upf_pk)

    def get_queryset(self):
        upf = self.get_upf()
        return MembroFamilia.objects.filter(upf=upf)

    def get_serializer_class(self):
        if self.action == "list":
            return MembroListSerializer
        return MembroDetailSerializer

    def perform_create(self, serializer):
        upf = self.get_upf()
        if not upf.ativa:
            raise serializers.ValidationError(
                "Não é possível adicionar membros a uma UPF inativa"
            )
        try:
            instance = serializer.save(upf=upf, criado_por=self.request.user, ultima_origem="web")
        except IntegrityError as e:
            if "unique_cpf_global" in str(e):
                raise serializers.ValidationError(
                    {"cpf": "Já existe um membro cadastrado com este CPF"}
                )
            raise
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.create",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                None, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        if old.pk == old.upf.titular_id and "grau_parentesco" in serializer.validated_data:
            if serializer.validated_data["grau_parentesco"] != "titular":
                raise serializers.ValidationError(
                    {"grau_parentesco": "Não é possível alterar o parentesco do titular. Use o endpoint de transferência de titularidade."}
                )
        valores_anteriores = {
            "membro_id": old.pk,
            "upf_id": old.upf_id,
            "nome_completo": old.nome_completo,
            "grau_parentesco": old.grau_parentesco,
            "cpf": old.cpf,
        }
        anteriores_sensiveis = {"saude": old.saude, "cor_raca": old.cor_raca}
        try:
            instance = serializer.save(ultima_origem="web")
        except IntegrityError as e:
            if "unique_cpf_global" in str(e):
                raise serializers.ValidationError(
                    {"cpf": "Já existe um membro cadastrado com este CPF"}
                )
            raise

        # Nunca grava o valor de saúde/cor-raça, só o nome de quem mudou.
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.update",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                anteriores_sensiveis, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
            valores_anteriores=valores_anteriores,
        )

    def perform_destroy(self, instance):
        upf = instance.upf
        if upf.titular_id == instance.pk:
            outros = MembroFamilia.objects.filter(upf=upf).exclude(pk=instance.pk)
            if not outros.exists():
                raise serializers.ValidationError(
                    "Não é possível excluir o único titular da UPF"
                )
            raise serializers.ValidationError(
                "Transfira a titularidade para outro membro antes de excluir"
            )
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.delete",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                None, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
            valores_anteriores={
                "membro_id": instance.pk,
                "upf_id": instance.upf_id,
                "nome_completo": instance.nome_completo,
                "grau_parentesco": instance.grau_parentesco,
            },
        )
        instance.delete()

    @action(detail=False, methods=["get"], url_path="exportar")
    def exportar(self, request, upf_pk=None):
        """Exporta em CSV os membros de uma UPF específica (Issue #186)."""
        upf = self.get_upf()
        columns, rows = membro_export_rows_for_upf(upf, user=request.user)
        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"membros_upf_{upf.pk}_{timestamp}.csv"
        return _membros_csv_response(columns, rows, filename)

    @action(detail=False, methods=["get"], url_path="resumo")
    def resumo(self, request, upf_pk=None):
        from django.db.models import Count, Case, When, IntegerField, Value, Q
        from django.db.models.functions import Coalesce

        upf = self.get_upf()
        hoje = date.today()

        membros = MembroFamilia.objects.filter(upf=upf)

        total = membros.count()
        tem_titular = membros.filter(grau_parentesco="titular").exists()

        faixa_agg = membros.aggregate(
            faixa_0_11=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False) & Q(data_nascimento__gt=data_limite_aniversario(hoje, 12))
            ),
            faixa_12_17=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False)
                & Q(data_nascimento__lte=data_limite_aniversario(hoje, 12))
                & Q(data_nascimento__gt=data_limite_aniversario(hoje, 18))
            ),
            faixa_18_59=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False)
                & Q(data_nascimento__lte=data_limite_aniversario(hoje, 18))
                & Q(data_nascimento__gt=data_limite_aniversario(hoje, 60))
            ),
            faixa_60_mais=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False) & Q(data_nascimento__lte=data_limite_aniversario(hoje, 60))
            ),
            sem_data_nasc=Count("pk", filter=Q(data_nascimento__isnull=True)),
        )

        faixa_etaria = {
            "0-11": faixa_agg["faixa_0_11"],
            "12-17": faixa_agg["faixa_12_17"],
            "18-59": faixa_agg["faixa_18_59"],
            "60+": faixa_agg["faixa_60_mais"],
            "sem_data_nascimento": faixa_agg["sem_data_nasc"],
        }

        genero_agg = membros.aggregate(
            masculino=Count("pk", filter=Q(genero=1)),
            feminino=Count("pk", filter=Q(genero=2)),
            nao_binario=Count("pk", filter=Q(genero=3)),
            nao_informado=Count("pk", filter=Q(genero=4) | Q(genero__isnull=True)),
        )

        genero = {
            "masculino": genero_agg["masculino"],
            "feminino": genero_agg["feminino"],
            "nao_binario": genero_agg["nao_binario"],
            "nao_informado": genero_agg["nao_informado"],
        }

        return Response({
            "total_membros": total,
            "faixa_etaria": faixa_etaria,
            "genero": genero,
            "tem_titular": tem_titular,
        })

    @action(detail=False, methods=["post"], url_path="transferir-titularidade")
    def transferir_titularidade(self, request, upf_pk=None):
        novo_titular_id = request.data.get("novo_titular_id")
        if not novo_titular_id:
            raise serializers.ValidationError(
                {"novo_titular_id": "Campo obrigatório."}
            )

        with transaction.atomic():
            upf = UPF.objects.select_for_update().get(pk=self.kwargs["upf_pk"])
            upfs_visiveis = upfs_acessiveis_ao_usuario(request.user)
            if not upfs_visiveis.filter(pk=upf.pk).exists():
                from django.shortcuts import get_object_or_404
                get_object_or_404(UPF, pk=self.kwargs["upf_pk"])

            try:
                novo_titular = MembroFamilia.objects.select_for_update().get(
                    pk=novo_titular_id, upf=upf
                )
            except MembroFamilia.DoesNotExist:
                raise serializers.ValidationError(
                    {"novo_titular_id": "Membro não encontrado nesta UPF."}
                )

            if novo_titular.pk == upf.titular_id:
                raise serializers.ValidationError(
                    {"novo_titular_id": "Este membro já é o titular."}
                )

            antigo_titular = upf.titular
            if antigo_titular:
                antigo_titular = MembroFamilia.objects.select_for_update().get(pk=antigo_titular.pk)

            antigo_titular_grau_parentesco_anterior = antigo_titular.grau_parentesco if antigo_titular else None

            if antigo_titular:
                antigo_titular.grau_parentesco = "filho"
                antigo_titular.save(update_fields=["grau_parentesco"])
            novo_titular.grau_parentesco = "titular"
            novo_titular.save(update_fields=["grau_parentesco"])
            upf.titular = novo_titular
            upf.save(update_fields=["titular"])

        AuditLog.objects.create(
            user=request.user,
            acao="MEMBRO.transferir_titularidade",
            modulo="sgp",
            entidade="UPF",
            entidade_id=str(upf.pk),
            valores_anteriores={
                "upf_id": upf.pk,
                "antigo_titular_id": antigo_titular.pk if antigo_titular else None,
                "antigo_titular_nome": antigo_titular.nome_completo if antigo_titular else None,
                "antigo_titular_grau_parentesco": antigo_titular_grau_parentesco_anterior,
            },
            valores_novos={
                "upf_id": upf.pk,
                "novo_titular_id": novo_titular.pk,
                "novo_titular_nome": novo_titular.nome_completo,
                "novo_titular_grau_parentesco": "titular",
            },
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return Response({
            "detail": "Titularidade transferida com sucesso.",
            "novo_titular": {
                "id": novo_titular.pk,
                "nome_completo": novo_titular.nome_completo,
            },
            "antigo_titular": {
                "id": antigo_titular.pk,
                "nome_completo": antigo_titular.nome_completo,
            } if antigo_titular else None,
        })


class MembroExportView(APIView):
    """
    Exporta em CSV os membros de múltiplas UPFs dentro do escopo territorial
    do usuário — relatório demográfico agregado (Issue #186).
    """

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("territorio_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("municipio", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("projeto", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
        description=(
            "Exportação territorial agregada de membros, restrita às UPFs "
            "acessíveis ao usuário autenticado. Limitada a "
            f"{MEMBROS_EXPORT_UPF_LIMIT} UPFs por exportação — acima disso, "
            "restrinja por territorio_id, municipio ou projeto."
        ),
    )
    def get(self, request):
        query_serializer = MembroExportQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filtros = query_serializer.validated_data

        try:
            columns, rows = membro_export_rows_for_scope(user=request.user, **filtros)
        except ExportLimitExceeded as exc:
            return Response(
                {
                    "detail": (
                        f"A exportação abrange {exc.upf_count} UPFs, acima do limite "
                        f"de {exc.limit}. Restrinja por territorio_id, município ou "
                        "projeto."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"membros_{timestamp}.csv"
        return _membros_csv_response(columns, rows, filename)


class ProjetoViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]


class SGPChoicesView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        choices = {
            "genero": [{"value": v, "label": l} for v, l in GENERO_CHOICES],
            "cor_raca": [{"value": v, "label": l} for v, l in COR_RACA_CHOICES],
            "escolaridade": [{"value": v, "label": l} for v, l in ESCOLARIDADE_CHOICES],
            "dispositivo": [{"value": v, "label": l} for v, l in DISPOSITIVO_CHOICES],
            "pct": [{"value": v, "label": l} for v, l in PCT_CHOICES],
            "posse_terra": [{"value": v, "label": l} for v, l in POSSE_TERRA_CHOICES],
            "situacao_moradia": [{"value": v, "label": l} for v, l in SITUACAO_MORADIA_CHOICES],
            "tipo_moradia": [{"value": v, "label": l} for v, l in TIPO_MORADIA_CHOICES],
            "material_construcao": [{"value": v, "label": l} for v, l in MATERIAL_CONSTRUCAO_CHOICES],
            "energia": [{"value": v, "label": l} for v, l in ENERGIA_CHOICES],
            "agua": [{"value": v, "label": l} for v, l in AGUA_CHOICES],
            "grau_parentesco": [{"value": v, "label": l} for v, l in PARENTESCO_CHOICES],
            "saude": [{"value": v, "label": v} for v in SAUDE_CHOICES],
        }
        return Response(choices)

class ActivityViewSet(ActivityPhotoMixin, ActivityDocumentMixin, viewsets.ModelViewSet):
    """
    ViewSet de Atividades do SGP.

    GET/POST    /api/v1/sgp/atividades/
    GET/PATCH/PUT/DELETE /api/v1/sgp/atividades/{id}/

    Isolamento territorial (RLS):
        - super-admin / ugp: visualizam tudo
        - articulador-estadual: atividades nos estados do seu escopo
        - adt-acr: atividades nos territórios vinculados
    """
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = ActivityPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ActivityFilter
    ordering_fields = ["data_inicio", "data_fim", "criado_em", "titulo"]
    ordering = ["-data_inicio"]

    # Caminho do atributo territorio para _resolve_territorio_id das permissions
    _territorio_attr_path = "territorio_id"

    def get_serializer_class(self):
        if self.action == "list":
            return ActivityListSerializer
        return ActivityDetailSerializer

    def get_queryset(self):
        qs = Activity.objects.select_related(
            "acao", "acao__meta",
            "municipio", "municipio__territory", "municipio__state",
            "comunidade",
            "tecnico_responsavel",
            "criado_por",
        ).prefetch_related(
            "equipe_adicional",
            Prefetch(
                "upfs_participantes",
                queryset=UPF.objects.select_related(
                    "municipio", "municipio__state", "territorio", "titular"
                ),
            ),
            "membros_participantes",
            "parceiros_organizacoes",
            Prefetch(
                "fotos",
                queryset=ActivityPhoto.objects.filter(ativa=True).order_by(
                    "ordem", "criado_em"
                ),
            ),
            Prefetch(
                "documentos",
                queryset=ActivityDocument.objects.filter(ativo=True).order_by(
                    "-criado_em"
                ),
            ),
        ).filter(ativo=True)

        user = self.request.user

        # RLS — acesso global (sem filtro territorial)
        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        # RLS — articulador estadual: filtra por estados do usuário
        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return qs.none()
            return qs.filter(municipio__state__sigla__in=states)

        # RLS — ADT/ACR: filtra por territórios vinculados
        if user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            if not territories.exists():
                return qs.none()
            return qs.filter(municipio__territory__in=territories)

        raise PermissionDenied("Você não tem acesso ao módulo de Atividades do SGP.")

    def perform_create(self, serializer):
        instance = serializer.save(criado_por=self.request.user, ultima_origem="web")
        self._log_audit("activity.create", instance)
        self._enqueue_google_calendar_sync_if_needed(instance, created=True)

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = self._snapshot(old)
        google_calendar_anteriores = self._google_calendar_sync_snapshot(old)
        instance = serializer.save(ultima_origem="web")
        self._log_audit("activity.update", instance, valores_anteriores)
        self._enqueue_google_calendar_sync_if_needed(
            instance,
            created=False,
            valores_anteriores=google_calendar_anteriores,
        )

    def perform_destroy(self, instance):
        """Soft-delete via ativo=False."""
        valores_anteriores = self._snapshot(instance)
        instance.ativo = False
        instance.save(update_fields=["ativo"])
        self._log_audit("activity.soft_delete", instance, valores_anteriores)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _snapshot(instance) -> dict:
        return {
            "id": instance.pk,
            "titulo": instance.titulo,
            "status": instance.status,
            "tipo_atividade": instance.tipo_atividade,
            "municipio_id": instance.municipio_id,
            "acao_id": instance.acao_id,
            "tecnico_responsavel_id": instance.tecnico_responsavel_id,
            "data_inicio": instance.data_inicio.isoformat(),
            "data_fim": instance.data_fim.isoformat(),
            "ativo": instance.ativo,
        }

    def _log_audit(self, acao: str, instance, valores_anteriores: dict | None = None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="Activity",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=self._snapshot(instance),
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def _google_calendar_sync_snapshot(instance) -> dict:
        return {
            "status": instance.status,
            "data_inicio": instance.data_inicio.isoformat(),
            "data_fim": instance.data_fim.isoformat(),
            "municipio_id": instance.municipio_id,
            "comunidade_id": instance.comunidade_id,
            "equipe_adicional_ids": sorted(
                instance.equipe_adicional.values_list("pk", flat=True)
            ),
        }

    def _enqueue_google_calendar_sync_if_needed(
        self,
        instance,
        *,
        created: bool,
        valores_anteriores: dict | None = None,
    ):
        if not get_config("google_calendar_integracao_ativa", False):
            return

        valores_novos = self._google_calendar_sync_snapshot(instance)
        if not self._should_sync_google_calendar(
            created,
            valores_anteriores,
            valores_novos,
        ):
            return

        Activity.objects.filter(pk=instance.pk).update(
            google_calendar_sync_status="pendente",
        )
        instance.google_calendar_sync_status = "pendente"
        try:
            sync_activity_to_google_calendar.delay(instance.pk)
        except Exception:
            logger.exception(
                "Falha ao enfileirar sync Google Calendar activity_id=%s.",
                instance.pk,
            )

    @staticmethod
    def _should_sync_google_calendar(
        created: bool,
        valores_anteriores: dict | None,
        valores_novos: dict,
    ) -> bool:
        status_atual = valores_novos["status"]
        if status_atual in {"cancelada", "nao_realizada"}:
            return bool(
                valores_anteriores
                and valores_anteriores["status"] != status_atual
            )

        if status_atual != "agendado":
            return False

        if created or not valores_anteriores:
            return True

        if valores_anteriores["status"] != "agendado":
            return True

        campos_monitorados = [
            "data_inicio",
            "data_fim",
            "municipio_id",
            "comunidade_id",
            "equipe_adicional_ids",
        ]
        return any(
            valores_anteriores[campo] != valores_novos[campo]
            for campo in campos_monitorados
        )

    # ── Endpoint de Calendário ────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="calendario")
    def calendario(self, request):
        """
        GET /api/v1/sgp/atividades/calendario/?inicio=YYYY-MM-DD&fim=YYYY-MM-DD

        Retorna payload reduzido de todas as atividades cujo intervalo
        (data_inicio, data_fim) intersecciona com o período solicitado.
        Máximo de 90 dias entre inicio e fim (retorna 400 se excedido).

        Filtros opcionais via querystring:
            tecnico_id, projeto, acao, tipo_atividade, status
        """
        from datetime import date, datetime, time
        from django.utils import timezone
        from rest_framework.fields import DateField as DRFDateField

        # ── Validação dos parâmetros de intervalo ───────────────────────────────
        errors = {}

        inicio_raw = request.query_params.get("inicio")
        fim_raw = request.query_params.get("fim")

        if not inicio_raw:
            errors["inicio"] = "Parâmetro obrigatório."
        if not fim_raw:
            errors["fim"] = "Parâmetro obrigatório."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        date_field = DRFDateField()
        try:
            inicio: date = date_field.to_internal_value(inicio_raw)
        except Exception:
            return Response(
                {"inicio": "Data inválida. Use o formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            fim: date = date_field.to_internal_value(fim_raw)
        except Exception:
            return Response(
                {"fim": "Data inválida. Use o formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fim < inicio:
            return Response(
                {"fim": "'fim' deve ser maior ou igual a 'inicio'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delta = (fim - inicio).days
        if delta > 90:
            return Response(
                {
                    "detail": (
                        f"Intervalo de {delta} dias excede o máximo permitido de 90 dias. "
                        f"Reduza o período e faça múltiplas requisições se necessário."
                    ),
                    "code": "CALENDAR_INTERVAL_TOO_LARGE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Queryset base (RLS já aplicado por get_queryset) ──────────────────────
        # Para o calendário não precisamos dos M2M pesados — override do QS
        qs = Activity.objects.select_related(
            "municipio",
            "municipio__state",
            "comunidade",
            "tecnico_responsavel",
        ).filter(ativo=True)

        # RLS inline (mesma lógica de get_queryset, sem os prefetch_related desnecessarios)
        user = request.user
        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            pass  # sem filtro territorial
        elif user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            qs = qs.filter(municipio__state__sigla__in=states) if states else qs.none()
        elif user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            qs = qs.filter(municipio__territory__in=territories) if territories.exists() else qs.none()
        else:
            raise PermissionDenied("Você não tem acesso ao módulo de Atividades do SGP.")

        inicio_dt = timezone.make_aware(datetime.combine(inicio, time.min))
        fim_dt = timezone.make_aware(datetime.combine(fim, time.max))

        # Interseccão de intervalo: atividade toca o período se
        #   data_inicio <= fim  AND  data_fim >= inicio
        qs = qs.filter(data_inicio__lte=fim_dt, data_fim__gte=inicio_dt)

        # ── Filtros opcionais ──────────────────────────────────────────────────
        qp = request.query_params

        if tecnico_id := qp.get("tecnico_id"):
            qs = qs.filter(tecnico_responsavel_id=tecnico_id)

        if projeto := qp.get("projeto"):
            qs = qs.filter(acao__meta__projeto_id=projeto)

        if acao_id := qp.get("acao"):
            qs = qs.filter(acao_id=acao_id)

        if tipo_atividade := qp.get("tipo_atividade"):
            qs = qs.filter(tipo_atividade=tipo_atividade)

        if status_filter := qp.get("status"):
            qs = qs.filter(status=status_filter)

        # ── Serialização sem paginação ───────────────────────────────────────────
        qs = qs.order_by("data_inicio", "data_fim")
        serializer = ActivityCalendarioSerializer(qs, many=True)
        return Response(
            {
                "count": qs.count(),
                "inicio": str(inicio),
                "fim": str(fim),
                "results": serializer.data,
            }
        )
