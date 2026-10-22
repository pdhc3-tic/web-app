from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.serializers.dashboard import DashboardSerializer
from apps.sgd.services import dashboard as dashboard_service


class SgdDashboardView(APIView):
    """Visão "home" do SGD: fila "Aguardando minha ação", contadores por status,
    alertas de saldo (faixa amarela/vermelha) e demandas sem movimentação há
    5 dias úteis — tudo no escopo do perfil do usuário logado."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(responses=DashboardSerializer, summary="Painel consolidado do SGD")
    def get(self, request):
        return Response(DashboardSerializer(dashboard_service.montar_dashboard(request.user)).data)
