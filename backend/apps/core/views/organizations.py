import logging

from django_filters import rest_framework as django_filters
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from apps.core.permissions import IsArticuladorEstadual, IsSuperAdmin, IsUGP
from apps.core.selectors import organization_list
from apps.core.serializers import OrganizationSerializer
from apps.core.services.audit import log_audit


logger = logging.getLogger(__name__)


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD de Organizações (OSC) com RBAC e soft-delete."""

    serializer_class = OrganizationSerializer
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["nome", "cnpj"]
    filterset_fields = ["municipio__state", "territorios", "ativa", "tipo"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [(IsSuperAdmin | IsUGP | IsArticuladorEstadual)()]
        return [(IsSuperAdmin | IsUGP)()]

    def get_queryset(self):
        return organization_list(self.request.user, action=self.action)

    def perform_create(self, serializer):
        instance = serializer.save()
        territory_ids = list(instance.territorios.values_list("pk", flat=True))
        log_audit(
            user=self.request.user,
            acao="organization_created",
            modulo="core",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_novos={
                "organization_id": instance.pk,
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
                "territorios": territory_ids,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        old_territory_ids = sorted(old.territorios.values_list("pk", flat=True))
        valores_anteriores = {
            "nome": old.nome,
            "cnpj": old.cnpj,
            "tipo": old.tipo,
            "ativa": old.ativa,
            "territorios": old_territory_ids,
        }

        instance = serializer.save()
        new_territory_ids = sorted(instance.territorios.values_list("pk", flat=True))

        log_audit(
            user=self.request.user,
            acao="organization_updated",
            modulo="core",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_anteriores=valores_anteriores,
            valores_novos={
                "nome": instance.nome,
                "cnpj": instance.cnpj,
                "tipo": instance.tipo,
                "ativa": instance.ativa,
                "territorios": new_territory_ids,
            },
            request=self.request,
        )

    def perform_destroy(self, instance):
        valores_anteriores = {"nome": instance.nome, "ativa": instance.ativa}
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        log_audit(
            user=self.request.user,
            acao="organization_deleted",
            modulo="core",
            entidade="Organization",
            entidade_id=instance.pk,
            valores_anteriores=valores_anteriores,
            valores_novos={"nome": instance.nome, "ativa": False},
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

