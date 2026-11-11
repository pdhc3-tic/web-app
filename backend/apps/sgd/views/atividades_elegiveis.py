from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.generics import ListAPIView

from apps.core.permissions import IsADTInTerritory, IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.sgd.serializers.atividade_elegivel import AtividadeElegivelSerializer
from apps.sgd.services import demand as demand_service
from apps.sgp.pagination import ActivityPagination


class AtividadesElegiveisView(ListAPIView):
    """Busca de atividades para vincular a uma demanda, sem o recorte territorial da
    listagem do SGP. Mesmo perfil de quem cria demanda e mesma paginação do SGP."""

    permission_classes = [IsAuthenticatedActiveAccess, IsADTInTerritory | IsSuperAdmin]
    serializer_class = AtividadeElegivelSerializer
    pagination_class = ActivityPagination

    @extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Trecho do título."),
            OpenApiParameter(
                "status", OpenApiTypes.STR, many=True, explode=True,
                enum=list(demand_service.ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA),
                description="Repetível. Sem o parâmetro, as duas.",
            ),
        ],
        responses={200: AtividadeElegivelSerializer(many=True), 400: OpenApiTypes.OBJECT},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return demand_service.atividades_elegiveis(
            q=self.request.query_params.get("q", ""), status=self.request.query_params.getlist("status"),
        )
