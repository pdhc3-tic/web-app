from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.models import User
from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_role_slugs
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.filters import TecnicoFilter
from apps.sgp.models import Tecnico
from apps.sgp.pagination import TecnicoPagination
from apps.sgp.serializers import TecnicoSerializer
from apps.sgp.serializers.tecnico import UsuarioElegivelSerializer
from apps.sgp.services.access import ROLES_COM_ESCOPO, scope_queryset


def tecnicos_acessiveis_ao_usuario(user, role_slugs=None):
    """Retorna queryset de Tecnicos acessíveis ao usuário conforme regras territoriais.

    `Territory.estados` é `ArrayField` — `territorio__estados__overlap` é o
    lookup Postgres equivalente ao antigo loop Python que cruzava
    `Territory.objects.all()` contra os estados do usuário. `role_slugs`
    pode vir pré-computado (ver `TecnicoViewSet.get_queryset`) para evitar
    refazer a checagem de roles do usuário em outra query.
    """
    return scope_queryset(
        Tecnico.objects.all(),
        user,
        state_lookup="territorio__estados__overlap",
        territory_lookup="territorio__in",
        role_slugs=role_slugs,
        raise_on_no_role=False,
    )


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

    def perform_destroy(self, instance):
        """Soft-delete via ativo=False. Não afeta Activity.tecnico_responsavel (FK direta a User)."""
        instance.ativo = False
        instance.save(update_fields=["ativo"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.ativo:
            raise ErroComCodigo(
                "tecnico_ja_inativo",
                "Este técnico já está inativo.",
                status_code=status.HTTP_409_CONFLICT,
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="usuarios-elegiveis")
    def usuarios_elegiveis(self, request):
        """Usuários ativos que ainda não são técnicos — opções do cadastro.

        `Tecnico.user` é OneToOne, então quem já tem vínculo (mesmo inativo)
        não pode ganhar outro."""
        queryset = User.objects.filter(
            ativo=True, acesso_revogado=False, tecnico__isnull=True
        ).order_by("nome", "pk")
        q = request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(nome__icontains=q)
        page = self.paginate_queryset(queryset)
        serializer = UsuarioElegivelSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
