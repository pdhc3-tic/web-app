from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.models.municipality import Municipality
from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.models.demand import Demand
from apps.sgd.serializers.demand import DemandCreateSerializer, DemandSerializer, DemandUpdateSerializer
from apps.sgd.serializers.demand_request import (
    DemandRequestCreateSerializer,
    DemandRequestSerializer,
    DemandRequestUpdateSerializer,
)
from apps.sgd.services import demand as demand_service
from apps.sgd.services.approval import demand_visibility_scope
from apps.sgd.views.approval import DemandApprovalMixin
from apps.sgd.views.demand_document import DemandDocumentMixin
from apps.sgp.models import Activity
from apps.sgp.models.workplan import WorkPlanAcao


class DemandViewSet(DemandApprovalMixin, DemandDocumentMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get_queryset(self):
        qs = Demand.objects.select_related(
            "activity__municipio__territory", "activity__municipio__state",
            "activity__comunidade", "activity__tecnico_responsavel",
            "activity__acao__meta", "solicitante",
        ).prefetch_related("solicitacoes__rubrica")
        scope = demand_visibility_scope(self.request.user)
        if scope is not None:
            qs = qs.filter(scope)
        return qs.distinct()

    def list(self, request):
        qs = self.get_queryset()
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return Response(DemandSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(DemandSerializer(demand).data)

    def create(self, request):
        entrada = DemandCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        if dados.get("activity_id"):
            activity = get_object_or_404(Activity, pk=dados["activity_id"])
        else:
            activity = demand_service.criar_activity_inline(
                titulo=dados["activity_titulo"],
                tipo_atividade=dados["activity_tipo_atividade"],
                acao=get_object_or_404(WorkPlanAcao, pk=dados["activity_acao_id"]),
                municipio=get_object_or_404(Municipality, pk=dados["activity_municipio_id"]),
                data_prevista=dados["activity_data_prevista"],
                usuario=request.user,
            )

        demand = demand_service.criar_demanda(
            titulo=dados["titulo"], activity=activity,
            justificativa=dados.get("justificativa", ""), solicitante=request.user,
        )
        return Response(DemandSerializer(demand).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        if demand.solicitante_id != request.user.pk:
            raise PermissionDenied("Só o solicitante pode editar a demanda.")
        entrada = DemandUpdateSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        demand = demand_service.atualizar_demanda(demand, **entrada.validated_data)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="submeter")
    def submeter(self, request, pk=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        if demand.solicitante_id != request.user.pk:
            raise PermissionDenied("Só o solicitante pode submeter a demanda.")
        demand = demand_service.submeter_demanda(demand, usuario=request.user)
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancelar(self, request, pk=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        demand = demand_service.cancelar_demanda(
            demand, usuario=request.user, motivo=request.data.get("motivo", ""),
        )
        return Response(DemandSerializer(demand).data)

    @action(detail=True, methods=["get", "post"], url_path="solicitacoes")
    def solicitacoes(self, request, pk=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method == "GET":
            return Response(DemandRequestSerializer(demand.solicitacoes.all(), many=True).data)

        if demand.solicitante_id != request.user.pk:
            raise PermissionDenied("Só o solicitante pode adicionar solicitações.")
        entrada = DemandRequestCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        solicitacao = demand_service.adicionar_solicitacao(demand, **entrada.validated_data)
        return Response(DemandRequestSerializer(solicitacao).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"solicitacoes/(?P<solicitacao_id>\d+)")
    def solicitacao_detail(self, request, pk=None, solicitacao_id=None):
        demand = get_object_or_404(self.get_queryset(), pk=pk)
        if demand.solicitante_id != request.user.pk:
            raise PermissionDenied("Só o solicitante pode alterar solicitações.")
        solicitacao = get_object_or_404(demand.solicitacoes, pk=solicitacao_id)

        if request.method == "PATCH":
            entrada = DemandRequestUpdateSerializer(data=request.data, partial=True)
            entrada.is_valid(raise_exception=True)
            solicitacao = demand_service.atualizar_solicitacao(solicitacao, **entrada.validated_data)
            return Response(DemandRequestSerializer(solicitacao).data)

        demand_service.remover_solicitacao(solicitacao)
        return Response(status=status.HTTP_204_NO_CONTENT)
