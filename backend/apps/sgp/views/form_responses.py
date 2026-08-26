from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.filters import FormResponseFilter
from apps.sgp.models import FormResponse, UPF
from apps.sgp.pagination import HistoricoPagination
from apps.sgp.serializers import (
    AvailableFormSerializer,
    FormResponseDetailSerializer,
    FormResponseListSerializer,
    FormResponseReceiveSerializer,
)
from apps.sgp.services.forms import get_available_upf_forms


def accessible_upf_queryset(user):
    queryset = UPF.objects.select_related("municipio", "municipio__state", "territorio")

    if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
        return queryset

    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        return queryset.filter(municipio__state__sigla__in=states) if states else queryset.none()

    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        return queryset.filter(territorio__in=territories) if territories.exists() else queryset.none()

    raise PermissionDenied("Você não tem acesso ao módulo SGP.")


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
        return accessible_upf_queryset(self.request.user)

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


class AvailableFormListView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(responses=AvailableFormSerializer(many=True))
    def get(self, request):
        forms = get_available_upf_forms(request.user)
        return Response(AvailableFormSerializer(forms, many=True).data)


class FormResponseReceiveView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        request=FormResponseReceiveSerializer,
        responses={
            200: FormResponseDetailSerializer,
            201: FormResponseDetailSerializer,
        },
        description=(
            "Recebe uma resposta concluída do contrato `1.0`. "
            "Reenvios com a mesma combinação de `origem` e "
            "`resposta_id_origem` retornam o registro existente."
        ),
        examples=[
            OpenApiExample(
                "Resposta submetida pelo SCA",
                value={
                    "upf_id": 1,
                    "formulario_id": 10,
                    "formulario_nome": "Diagnóstico produtivo",
                    "formulario_versao": "1.0",
                    "respondente": "Técnico de campo",
                    "status": "submetido",
                    "respostas_json": {"atividade_principal": "Agricultura"},
                    "origem": "sca",
                    "contract_version": "1.0",
                    "resposta_id_origem": "sca-9c4f9c8d",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = FormResponseReceiveSerializer(
            data=request.data,
            context={"upf_queryset": accessible_upf_queryset(request.user)},
        )
        serializer.is_valid(raise_exception=True)
        form_response = serializer.save()
        response_status = (
            status.HTTP_201_CREATED if form_response._was_created else status.HTTP_200_OK
        )
        return Response(
            FormResponseDetailSerializer(form_response).data,
            status=response_status,
        )
