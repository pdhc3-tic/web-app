from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.sgd.serializers.erros import ERRO_DE_DOMINIO
from apps.sgd.serializers.individual_limit import DemandIndividualLimitSerializer
from apps.sgd.services import orcamento as orcamento_service
from apps.sgp.models import SpendingLimit

JUSTIFICATIVA_DA_ROTA = "Definido pela rota de limites individuais do SGD."


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("solicitante", OpenApiTypes.INT, description="Id do usuário.")],
        responses=DemandIndividualLimitSerializer(many=True),
    ),
    create=extend_schema(
        request=DemandIndividualLimitSerializer,
        responses={201: DemandIndividualLimitSerializer, 400: ERRO_DE_DOMINIO},
    ),
    partial_update=extend_schema(
        request=DemandIndividualLimitSerializer,
        responses={200: DemandIndividualLimitSerializer, 400: ERRO_DE_DOMINIO},
    ),
)
class DemandIndividualLimitViewSet(viewsets.ViewSet):
    """Alias de `/sgp/orcamento/limites/` para as linhas individuais do período vigente,
    enquanto o front migra. A rota antiga não pede justificativa: ela é preenchida aqui."""

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    # Só para o drf-spectacular: o tipo do `{id}` e a lista sem paginação.
    queryset = SpendingLimit.objects.none()
    pagination_class = None

    def list(self, request):
        hoje = orcamento_service.hoje()
        qs = SpendingLimit.objects.select_related("rubrica", "user").filter(
            escopo=SpendingLimit.Escopo.INDIVIDUAL, periodo_inicio__lte=hoje, periodo_fim__gte=hoje,
        )
        solicitante_id = request.query_params.get("solicitante")
        if solicitante_id:
            qs = qs.filter(user_id=solicitante_id)
        return Response(DemandIndividualLimitSerializer(qs, many=True).data)

    def create(self, request):
        serializer = DemandIndividualLimitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        limite = orcamento_service.criar_sobrescrita(
            user=dados["user"], rubrica=dados["rubrica"], valor_limite=dados["valor_limite"],
            justificativa=JUSTIFICATIVA_DA_ROTA, usuario=request.user,
        )
        return Response(DemandIndividualLimitSerializer(limite).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        # Travado antes de gravar, para não perder uma reserva concorrente.
        with transaction.atomic():
            limite = get_object_or_404(
                SpendingLimit.objects.select_for_update(of=("self",)).filter(escopo=SpendingLimit.Escopo.INDIVIDUAL),
                pk=pk,
            )
            serializer = DemandIndividualLimitSerializer(limite, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            novo = serializer.validated_data.get("valor_limite", limite.valor_limite)
            limite = orcamento_service.alterar_sobrescrita(
                limite.pk, valor_limite=novo, justificativa=JUSTIFICATIVA_DA_ROTA, usuario=request.user,
            )
        return Response(DemandIndividualLimitSerializer(limite).data)
