from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.filters import FormResponseFilter
from apps.sgp.models import FormResponse, UPF
from apps.sgp.pagination import HistoricoPagination
from apps.sgp.serializers import FormResponseDetailSerializer, FormResponseListSerializer


class FormResponseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = HistoricoPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = FormResponseFilter
    http_method_names = ["get", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FormResponseDetailSerializer
        return FormResponseListSerializer

    def _accessible_upf_queryset(self):
        queryset = UPF.objects.select_related("municipio", "municipio__state", "territorio")
        user = self.request.user

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return queryset

        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            return queryset.filter(municipio__state__sigla__in=states) if states else queryset.none()

        if user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            return queryset.filter(territorio__in=territories) if territories.exists() else queryset.none()

        raise PermissionDenied("Você não tem acesso ao módulo SGP.")

    def get_upf(self):
        if not hasattr(self, "_upf"):
            self._upf = get_object_or_404(
                self._accessible_upf_queryset(),
                pk=self.kwargs["upf_pk"],
            )
        return self._upf

    def get_queryset(self):
        return FormResponse.objects.filter(upf=self.get_upf()).order_by(
            "-data_preenchimento", "-pk"
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("formulario_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("respondente", OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        responses=FormResponseListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(responses=FormResponseDetailSerializer)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
