from rest_framework import viewsets

from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin, IsUGP
from apps.sgp.models import Projeto
from apps.sgp.serializers import ProjetoSerializer


class ProjetoViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]
