from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.models.territory import Territory
from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.filters import TecnicoFilter
from apps.sgp.models import Tecnico
from apps.sgp.serializers import TecnicoSerializer


def tecnicos_acessiveis_ao_usuario(user):
    """Retorna queryset de Tecnicos acessíveis ao usuário conforme regras territoriais."""
    qs = Tecnico.objects.all()
    if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
        return qs
    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        if not states:
            return qs.none()
        territorio_ids = [
            t.pk for t in Territory.objects.all() if set(t.estados or []) & states
        ]
        return qs.filter(territorio_id__in=territorio_ids)
    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        if not territories.exists():
            return qs.none()
        return qs.filter(territorio__in=territories)
    return qs.none()


class TecnicoViewSet(viewsets.ModelViewSet):
    serializer_class = TecnicoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TecnicoFilter
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        user = self.request.user
        if not (
            user_has_role(user, "super-admin")
            or user_has_role(user, "ugp")
            or user_has_role(user, "articulador-estadual")
            or user_has_role(user, "adt-acr")
        ):
            raise PermissionDenied("Você não tem acesso ao módulo de Técnicos do SGP.")
        return tecnicos_acessiveis_ao_usuario(user).select_related("user", "territorio", "osc")

    def perform_destroy(self, instance):
        """Soft-delete via ativo=False. Não afeta Activity.tecnico_responsavel (FK direta a User)."""
        instance.ativo = False
        instance.save(update_fields=["ativo"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
