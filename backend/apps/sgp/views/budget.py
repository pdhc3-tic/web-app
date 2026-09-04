from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role
from apps.sgp.models import BudgetAllocation, WorkPlanMeta
from apps.sgp.serializers_budget import (
    BudgetAllocationCreateSerializer,
    BudgetAllocationSerializer,
    BudgetAllocationUpdateSerializer,
)
from apps.sgp.services import budget as budget_service


class BudgetAllocationViewSet(viewsets.ViewSet):
    """`create` aninhada em `metas/{id}/orcamento/alocacoes/`,
    `partial_update`/`destroy` em `orcamento/alocacoes/{id}/`. Wiring
    manual em urls.py, sem router."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def _autorizar(self, request, *, nivel, estado, territorio):
        user = request.user
        if budget_service.is_global_budget_user(user):
            return

        if nivel != BudgetAllocation.Nivel.TERRITORIAL:
            raise PermissionDenied(
                "Só UGP/Super Admin criam ou alteram alocações nacionais/estaduais."
            )
        if not user_has_role(user, "articulador-estadual"):
            raise PermissionDenied("Você não tem permissão para gerenciar alocações.")

        estados_do_territorio = set((territorio.estados if territorio else []) or [])
        if not estados_do_territorio & budget_service.allowed_states_for_user(user):
            raise PermissionDenied("Este território não pertence ao seu estado.")

    @extend_schema(
        request=BudgetAllocationCreateSerializer,
        responses={201: BudgetAllocationSerializer},
    )
    def create(self, request, meta_pk=None):
        meta = get_object_or_404(WorkPlanMeta, pk=meta_pk)
        entrada = BudgetAllocationCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        self._autorizar(
            request, nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
        )

        allocation = budget_service.criar_alocacao(
            meta=meta, rubrica=dados["rubrica"], nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
            valor_alocado=dados["valor_alocado"], usuario=request.user,
            reserva_ugp=dados.get("reserva_ugp", False),
        )
        return Response(
            BudgetAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=BudgetAllocationUpdateSerializer,
        responses={200: BudgetAllocationSerializer},
    )
    def partial_update(self, request, pk=None):
        allocation = get_object_or_404(BudgetAllocation, pk=pk)
        self._autorizar(
            request, nivel=allocation.nivel,
            estado=allocation.estado, territorio=allocation.territorio,
        )

        entrada = BudgetAllocationUpdateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        allocation = budget_service.atualizar_valor_alocado(
            allocation,
            novo_valor=entrada.validated_data["valor_alocado"],
            usuario=request.user,
        )
        return Response(BudgetAllocationSerializer(allocation).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        allocation = get_object_or_404(BudgetAllocation, pk=pk)
        self._autorizar(
            request, nivel=allocation.nivel,
            estado=allocation.estado, territorio=allocation.territorio,
        )
        budget_service.remover_alocacao(allocation)
        return Response(status=status.HTTP_204_NO_CONTENT)
