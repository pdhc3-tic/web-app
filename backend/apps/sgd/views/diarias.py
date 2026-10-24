from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsADTInTerritory, IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.sgd.serializers.diarias import SimulacaoDiariasSerializer, SimularDiariasQuerySerializer
from apps.sgd.services.demand_request import calcular_diarias

# Até a tabela de diárias por faixa de destino existir, todo destino usa o
# valor padrão do SystemConfig.
FAIXA_UNICA = {"id": None, "nome": "Valor padrão"}


class SimularDiariasView(APIView):
    """Valor das diárias para o formulário, com a mesma regra usada ao gravar a solicitação."""

    permission_classes = [IsAuthenticatedActiveAccess, IsADTInTerritory | IsSuperAdmin]

    @extend_schema(
        parameters=[SimularDiariasQuerySerializer],
        responses={200: SimulacaoDiariasSerializer, 400: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        query = SimularDiariasQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        diarias = calcular_diarias(**query.validated_data)
        return Response(SimulacaoDiariasSerializer({
            "faixa_destino": FAIXA_UNICA,
            "valor_por_diaria": diarias.valor_por_diaria,
            "numero_diarias": diarias.numero,
            "valor_total": diarias.valor_total,
        }).data)
