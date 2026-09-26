from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_role_slugs
from apps.sgp.filters import TecnicoFilter
from apps.sgp.pagination import TecnicoPagination
from apps.sgp.serializers import TecnicoSerializer
from apps.sgp.serializers.tecnico import UsuarioElegivelSerializer
from apps.sgp.services.access import ROLES_COM_ESCOPO, tecnicos_acessiveis_ao_usuario
from apps.sgp.services.tecnico import desativar_tecnico, usuarios_elegiveis_a_tecnico


class TecnicoViewSet(viewsets.ModelViewSet):
    serializer_class = TecnicoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TecnicoFilter
    pagination_class = TecnicoPagination
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'usuarios_elegiveis'):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        user = self.request.user
        role_slugs = user_role_slugs(user, ROLES_COM_ESCOPO)
        if not role_slugs:
            raise PermissionDenied("Você não tem acesso ao módulo de Técnicos do SGP.")
        return tecnicos_acessiveis_ao_usuario(user, role_slugs=role_slugs).select_related(
            "user", "territorio", "osc"
        )

    def destroy(self, request, *args, **kwargs):
        desativar_tecnico(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="usuarios-elegiveis")
    def usuarios_elegiveis(self, request):
        queryset = usuarios_elegiveis_a_tecnico(request.query_params.get("q", ""))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(UsuarioElegivelSerializer(page, many=True).data)
