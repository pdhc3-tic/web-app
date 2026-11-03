from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.core.permissions import IsSuperAdmin
from apps.sgd.serializers.individual_limit import DemandIndividualLimitSerializer
from apps.sgd.services import orcamento as orcamento_service
from apps.sgp.models import SpendingLimit

JUSTIFICATIVA_DA_ROTA = "Definido pela rota de limites individuais do SGD."


class DemandIndividualLimitViewSet(viewsets.ViewSet):
    """Alias de `/sgp/orcamento/limites/` para as linhas individuais do período vigente,
    enquanto o front migra. A rota antiga não pede justificativa: ela é preenchida aqui."""

    permission_classes = [IsSuperAdmin]

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
        # Travado antes de validar: a redução é conferida contra o comprometido em vigor,
        # sem perder uma reserva concorrente.
        with transaction.atomic():
            limite = get_object_or_404(SpendingLimit.objects.select_for_update(of=("self",)), pk=pk)
            serializer = DemandIndividualLimitSerializer(limite, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            novo = serializer.validated_data.get("valor_limite", limite.valor_limite)
            limite = orcamento_service.alterar_sobrescrita(
                limite.pk, valor_limite=novo, justificativa=JUSTIFICATIVA_DA_ROTA, usuario=request.user,
            )
        return Response(DemandIndividualLimitSerializer(limite).data)
