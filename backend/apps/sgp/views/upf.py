from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.membro_audit import log_membro_change, sensitive_fields_changed
from apps.core.services.permissions import user_role_slugs, user_states, user_territories
from apps.sgp.cache import UPF_MAP_CACHE_TIMEOUT, build_upf_map_cache_key
from apps.sgp.filters import UPFFilter
from apps.sgp.models import UPF
from apps.sgp.pagination import UPFPagination
from apps.sgp.serializers import HistoricoEntrySerializer, MunicipioNestedSerializer, UPFDetailSerializer, UPFListSerializer
from apps.sgp.views.upf_foto import UPFPhotoMixin
from apps.sgp.views.upf_historico import UPFHistoricoMixin

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


class UPFViewSet(UPFPhotoMixin, UPFHistoricoMixin, viewsets.ModelViewSet):
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
