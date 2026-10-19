from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.core.utils import get_client_ip
from apps.sgd.models.demand_type_rubrica_mapping import DemandTypeRubricaMapping
from apps.sgd.serializers.demand_type_rubrica_mapping import DemandTypeRubricaMappingSerializer


@extend_schema_view(
    list=extend_schema(tags=["SGD - Configuração"], summary="Lista os mapeamentos tipo → rubrica"),
    create=extend_schema(tags=["SGD - Configuração"], summary="Cria um mapeamento tipo → rubrica"),
    retrieve=extend_schema(tags=["SGD - Configuração"], summary="Detalha um mapeamento tipo → rubrica"),
    partial_update=extend_schema(tags=["SGD - Configuração"], summary="Altera um mapeamento tipo → rubrica"),
    destroy=extend_schema(tags=["SGD - Configuração"], summary="Remove um mapeamento tipo → rubrica"),
)
class DemandTypeRubricaMappingViewSet(viewsets.ModelViewSet):
    """Painel de configuração do mapeamento tipo de solicitação → rubrica (SGD §3). Só Super Admin."""

    queryset = DemandTypeRubricaMapping.objects.select_related("rubrica")
    serializer_class = DemandTypeRubricaMappingSerializer
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("tipo"):
            qs = qs.filter(tipo=params["tipo"])
        if params.get("ativo") in ("true", "false"):
            qs = qs.filter(ativo=params["ativo"] == "true")
        return qs

    def _auditar(self, acao, pk, anteriores=None, novos=None):
        AuditLog.objects.create(
            user=self.request.user, acao=f"tipo_rubrica.{acao}", modulo="sgd", entidade="DemandTypeRubricaMapping",
            entidade_id=str(pk), valores_anteriores=anteriores or {}, valores_novos=novos or {},
            ip=get_client_ip(self.request), user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def _dados(instancia):
        return DemandTypeRubricaMappingSerializer(instancia).data

    @transaction.atomic
    def perform_create(self, serializer):
        instancia = serializer.save()
        self._auditar("criado", instancia.pk, novos=self._dados(instancia))

    @transaction.atomic
    def perform_update(self, serializer):
        anteriores = self._dados(serializer.instance)
        instancia = serializer.save()
        self._auditar("alterado", instancia.pk, anteriores=anteriores, novos=self._dados(instancia))

    @transaction.atomic
    def perform_destroy(self, instance):
        anteriores, pk = self._dados(instance), instance.pk
        instance.delete()
        self._auditar("removido", pk, anteriores=anteriores)
