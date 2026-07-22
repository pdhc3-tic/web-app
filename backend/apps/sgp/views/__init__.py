import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, generics, serializers, status, viewsets
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.cache import UPF_MAP_CACHE_TIMEOUT, build_upf_map_cache_key
from apps.sgp.filters import ActivityFilter, UPFFilter
from apps.sgp.models import (
    Activity, Comunidade, Cultura, EspecieAnimal, MembroFamilia, UPF, Projeto
)
from apps.sgp.pagination import (
    ActivityPagination, CatalogoPagination, HistoricoPagination, UPFPagination
)
from apps.sgp.serializers import (
    ActivityDetailSerializer,
    ActivityListSerializer,
    ComunidadeSerializer,
    CulturaSerializer,
    EspecieAnimalSerializer,
    HistoricoEntrySerializer,
    MembroDetailSerializer,
    MembroListSerializer,
    ProjetoSerializer,
    UPFDetailSerializer,
    UPFListSerializer,
)
from .upf_foto import UPFPhotoMixin
from .upf_documentos import UPFDocumentViewSet
from .production import ProductionViewSet

logger = logging.getLogger("apps.sgp.views")


class QSearchFilter(filters.SearchFilter):
    search_param = 'q'


class CatalogoListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
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


class UPFViewSet(UPFPhotoMixin, viewsets.ModelViewSet):
    MAPA_FEATURE_LIMIT = 10000
    queryset = UPF.objects.select_related(
        "municipio", "municipio__state", "territorio", "projeto", "criado_por"
    ).all()
    permission_classes = [IsAuthenticated]
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

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return qs.none()
            return qs.filter(municipio__state__sigla__in=states)

        if user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            if not territories.exists():
                return qs.none()
            return qs.filter(territorio__in=territories)

        raise PermissionDenied("Você não tem acesso ao módulo SGP.")

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
                    "features": serializers.ListField(
                        child=serializers.DictField(),
                    ),
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
            .select_related("titular", "municipio", "territorio")
            .only(
                "id",
                "titular",
                "titular__nome_completo",
                "latitude",
                "longitude",
                "municipio",
                "municipio__nome",
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
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(upf.longitude), float(upf.latitude)],
            },
            "properties": {
                "id": upf.pk,
                "nome_titular": upf.titular.nome_completo,
                "municipio": upf.municipio.nome,
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
        instance = serializer.save(criado_por=self.request.user)
        self._log_audit("UPF.create", instance)

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
        instance = serializer.save()
        self._log_audit("UPF.update", instance, valores_anteriores)

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
        return [IsAuthenticated()]

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


class MembroViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_upf(self):
        return get_object_or_404(UPF, pk=self.kwargs["upf_pk"])

    def get_queryset(self):
        return MembroFamilia.objects.filter(upf=self.kwargs["upf_pk"])

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
        instance = serializer.save(upf=upf, criado_por=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.create",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_novos={
                "membro_id": instance.pk,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
                "upf_id": instance.upf_id,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "membro_id": old.pk,
            "upf_id": old.upf_id,
            "nome_completo": old.nome_completo,
            "parentesco": old.parentesco,
            "cpf": old.cpf,
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.update",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                "membro_id": instance.pk,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
                "upf_id": instance.upf_id,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.delete",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_anteriores={
                "membro_id": instance.pk,
                "upf_id": instance.upf_id,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
            },
            valores_novos={},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
        instance.delete()


class ProjetoViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticated()]


class ActivityViewSet(viewsets.ModelViewSet):
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
    permission_classes = [IsAuthenticated]
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
            "municipio", "municipio__territory",
            "comunidade",
            "tecnico_responsavel",
            "criado_por",
        ).prefetch_related(
            "equipe_adicional",
            "upfs_participantes",
            "membros_participantes",
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
        instance = serializer.save(criado_por=self.request.user)
        self._log_audit("activity.create", instance)

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = self._snapshot(old)
        instance = serializer.save()
        self._log_audit("activity.update", instance, valores_anteriores)

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
            "data_inicio": str(instance.data_inicio),
            "data_fim": str(instance.data_fim),
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
