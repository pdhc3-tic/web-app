from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.permissions import IsSuperAdmin
from apps.sgd.models.individual_limit import DemandIndividualLimit
from apps.sgd.serializers.individual_limit import DemandIndividualLimitSerializer
from apps.sgd.services import auditoria as auditoria_service


class DemandIndividualLimitViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    def list(self, request):
        qs = DemandIndividualLimit.objects.select_related("rubrica", "solicitante")
        solicitante_id = request.query_params.get("solicitante")
        if solicitante_id:
            qs = qs.filter(solicitante_id=solicitante_id)
        return Response(DemandIndividualLimitSerializer(qs, many=True).data)

    def create(self, request):
        serializer = DemandIndividualLimitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                limite = serializer.save(criado_por=request.user)
                auditoria_service.registrar_limite_criado(limite, usuario=request.user)
        except IntegrityError as exc:
            # O recurso extra cria o limite com `get_or_create`: a validação de
            # unicidade passa e o insert concorrente bate na constraint.
            raise ValidationError(
                {"rubrica": "Já existe um limite individual deste solicitante nesta rubrica."}
            ) from exc
        return Response(DemandIndividualLimitSerializer(limite).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        # Travado e relido: o save grava todos os campos, e um `valor_comprometido`
        # lido antes de uma reserva concorrente apagaria essa reserva.
        with transaction.atomic():
            limite = get_object_or_404(DemandIndividualLimit.objects.select_for_update(), pk=pk)
            valor_anterior = limite.valor_limite
            serializer = DemandIndividualLimitSerializer(limite, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            limite = serializer.save()
            if limite.valor_limite != valor_anterior:
                auditoria_service.registrar_limite_alterado(
                    limite, valor_anterior=valor_anterior, usuario=request.user,
                )
        return Response(serializer.data)
