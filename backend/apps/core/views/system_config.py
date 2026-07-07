from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.core.models.system_config import SystemConfig
from apps.core.permissions import IsSuperAdminOrUGPReadOnly
from apps.core.serializers import SystemConfigSerializer


class SystemConfigListView(generics.ListAPIView):
    """GET /api/v1/system-config/ — lista configurações do sistema."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [IsAuthenticated, IsSuperAdminOrUGPReadOnly]


class SystemConfigDetailView(generics.RetrieveUpdateAPIView):
    """GET|PATCH /api/v1/system-config/{chave}/ — detalhe ou atualização."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    lookup_field = "chave"
    http_method_names = ["get", "patch"]
    permission_classes = [IsAuthenticated, IsSuperAdminOrUGPReadOnly]

    def perform_update(self, serializer):
        serializer.save(atualizado_por=self.request.user)
