from rest_framework import generics

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role
from apps.sgp.models import Cultura, EspecieAnimal
from apps.sgp.pagination import CatalogoPagination
from apps.sgp.serializers import CulturaSerializer, EspecieAnimalSerializer


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
