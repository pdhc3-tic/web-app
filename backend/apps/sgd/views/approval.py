from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsArticuladorEstadual, IsAuthenticatedActiveAccess, IsFGD, IsUGP
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.serializers.approval import (
    AutorizarExcedenteSerializer,
    AutorizarSerializer,
    ConcluirSerializer,
    DevolverSerializer,
    PreviewDecisaoSerializer,
    RecusarSerializer,
)
from apps.sgd.serializers.demand import DemandSerializer
from apps.sgd.services import approval as approval_service
from apps.sgd.services import balance as balance_service
from apps.sgp.models.budget import BudgetAllocation


class DemandApprovalMixin:
    # Uma role por action, além de IsAuthenticatedActiveAccess (sempre
    # exigida) — o host (DemandViewSet) delega pra cá em get_permissions()
    # quando a action está aqui, senão usa a permissão padrão dele.
    _PERMISSAO_POR_ACTION = {
        "pre_autorizar": IsArticuladorEstadual,
        "devolver": IsArticuladorEstadual,
        "autorizar": IsUGP,
        "recusar": IsUGP,
        "autorizar_excedente": IsUGP,
        "atender": IsFGD,
        "concluir": IsFGD,
    }

    def get_permissions(self):
        role_permission = self._PERMISSAO_POR_ACTION.get(self.action)
        if role_permission is not None:
            return [IsAuthenticatedActiveAccess(), role_permission()]
        return super().get_permissions()

    def _get_demand(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    @action(detail=True, methods=["post"], url_path="pre-autorizar")
    def pre_autorizar(self, request, pk=None):
        demand = self._get_demand(pk)
        demand = approval_service.pre_autorizar(demand, responsavel=request.user)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="devolver")
    def devolver(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = DevolverSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = approval_service.devolver(demand, responsavel=request.user, **entrada.validated_data)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="autorizar")
    def autorizar(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = AutorizarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = approval_service.autorizar(demand, responsavel=request.user, **entrada.validated_data)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="recusar")
    def recusar(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = RecusarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = approval_service.recusar(demand, responsavel=request.user, **entrada.validated_data)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="autorizar-excedente")
    def autorizar_excedente(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = AutorizarExcedenteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        solicitacao = get_object_or_404(DemandRequest, pk=dados["demand_request_id"], demanda=demand)
        origem = get_object_or_404(BudgetAllocation, pk=dados["origem_allocation_id"])
        balance_service.autorizar_excedente(
            demand_request=solicitacao, origem_allocation=origem,
            valor_excedente=dados["valor_excedente"], justificativa=dados["justificativa"],
            usuario=request.user,
        )
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="atender")
    def atender(self, request, pk=None):
        demand = self._get_demand(pk)
        demand = approval_service.atender(demand, responsavel=request.user)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="concluir")
    def concluir(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = ConcluirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = approval_service.concluir(demand, responsavel=request.user, **entrada.validated_data)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["get"], url_path="preview-decisao")
    def preview_decisao(self, request, pk=None):
        demand = self._get_demand(pk)
        query = PreviewDecisaoSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        solicitacao = get_object_or_404(
            DemandRequest, pk=query.validated_data["demand_request_id"], demanda=demand,
        )
        preview = approval_service.preview_impacto(solicitacao, query.validated_data["valor"])
        return Response(preview)
