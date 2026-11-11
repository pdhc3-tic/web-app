from drf_spectacular.utils import extend_schema
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.core.permissions import IsADTInTerritory, IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.sgd.serializers.atividade_elegivel import (
    AtividadeElegivelDetalheSerializer,
    AtividadeElegivelSerializer,
    AtividadesElegiveisQuerySerializer,
)
from apps.sgd.services import demand as demand_service
from apps.sgp.pagination import ActivityPagination

# Mesmo perfil de quem cria demanda.
_PERMISSOES = [IsAuthenticatedActiveAccess, IsADTInTerritory | IsSuperAdmin]


class AtividadesElegiveisView(ListAPIView):
    """Busca de atividades para vincular a uma demanda, sem o recorte territorial da
    listagem do SGP. Mesma paginação e ordenação do SGP."""

    permission_classes = _PERMISSOES
    serializer_class = AtividadeElegivelSerializer
    pagination_class = ActivityPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ["data_inicio", "titulo"]
    ordering = ["-data_inicio", "-pk"]

    @extend_schema(parameters=[AtividadesElegiveisQuerySerializer])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        query = AtividadesElegiveisQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        return demand_service.atividades_elegiveis(**query.validated_data)


class AtividadeElegivelDetalheView(RetrieveAPIView):
    """A atividade escolhida, em qualquer status: o formulário mostra a regra do status
    (bloqueio ou justificativa de despesa posterior)."""

    permission_classes = _PERMISSOES
    serializer_class = AtividadeElegivelDetalheSerializer

    def get_queryset(self):
        return demand_service.atividades_para_vincular().select_related(
            "municipio__state", "municipio__territory", "comunidade", "tecnico_responsavel",
            "acao__meta", "acao__submeta", "acao__indicador",
        )
