from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsArticuladorEstadual, IsAuthenticatedActiveAccess, IsFGD, IsUGP
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.serializers.approval import (
    AutorizarSerializer,
    ConcluirSerializer,
    ContagemAguardandoSerializer,
    DevolverSerializer,
    PreviewDecisaoRespostaSerializer,
    PreviewDecisaoSerializer,
    RecusarSerializer,
)
from apps.sgd.serializers.demand import DemandSerializer
from apps.sgd.serializers.erros import ERRO_DE_DOMINIO, SALDO_INSUFICIENTE
from apps.sgd.services import approval as approval_service
from apps.sgd.services import workflow as workflow_service


class DemandApprovalMixin:
    # Uma role por action, além de IsAuthenticatedActiveAccess (sempre
    # exigida) — o host (DemandViewSet) delega pra cá em get_permissions()
    # quando a action está aqui, senão usa a permissão padrão dele.
    _PERMISSAO_POR_ACTION = {
        "pre_autorizar": IsArticuladorEstadual,
        "devolver": IsArticuladorEstadual,
        "autorizar": IsUGP,
        "recusar": IsUGP,
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

    @extend_schema(filters=False, responses=ContagemAguardandoSerializer)
    @action(detail=False, methods=["get"], url_path="aguardando-minha-acao/contagem", pagination_class=None)
    def aguardando_minha_acao_contagem(self, request):
        demandas = approval_service.demandas_aguardando_acao(request.user, self.get_queryset())
        return Response({
            "total": demandas.count(),
            "status": approval_service.status_aguardando_acao(request.user),
        })

    @extend_schema(request=None, responses={200: DemandSerializer, 400: ERRO_DE_DOMINIO})
    @action(detail=True, methods=["post"], url_path="pre-autorizar")
    def pre_autorizar(self, request, pk=None):
        demand = self._get_demand(pk)
        demand = workflow_service.executar_transicao(demand, "pre_autorizada", ator=request.user)
        return Response(DemandSerializer(demand).data)

    @extend_schema(request=DevolverSerializer, responses={200: DemandSerializer, 400: ERRO_DE_DOMINIO})
    @action(detail=True, methods=["post"], url_path="devolver")
    def devolver(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = DevolverSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = workflow_service.executar_transicao(
            demand, "devolvida", ator=request.user, **entrada.validated_data,
        )
        return Response(DemandSerializer(demand).data)

    @extend_schema(
        request=AutorizarSerializer,
        responses={200: DemandSerializer, 400: SALDO_INSUFICIENTE},
        description=(
            "Ajusta a reserva ao valor autorizado. Com `excedente_autorizado`, o que passa do limite "
            "sai de `origem_allocation` (SGD-RF16)."
        ),
    )
    @action(detail=True, methods=["post"], url_path="autorizar")
    def autorizar(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = AutorizarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = workflow_service.executar_transicao(
            demand, "autorizada", ator=request.user, **entrada.validated_data,
        )
        return Response(DemandSerializer(demand).data)

    @extend_schema(request=RecusarSerializer, responses={200: DemandSerializer, 400: ERRO_DE_DOMINIO})
    @action(detail=True, methods=["post"], url_path="recusar")
    def recusar(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = RecusarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = workflow_service.executar_transicao(
            demand, "recusada", ator=request.user, **entrada.validated_data,
        )
        return Response(DemandSerializer(demand).data)

    @extend_schema(request=None, responses={200: DemandSerializer, 400: ERRO_DE_DOMINIO})
    @action(detail=True, methods=["post"], url_path="atender")
    def atender(self, request, pk=None):
        demand = self._get_demand(pk)
        demand = workflow_service.executar_transicao(demand, "em_atendimento", ator=request.user)
        return Response(DemandSerializer(demand).data)

    @extend_schema(
        request=ConcluirSerializer,
        responses={200: DemandSerializer, 400: ERRO_DE_DOMINIO},
        description=(
            "Executa por `min(pago, autorizado)` e devolve a diferença ao saldo. O que for pago acima "
            "do autorizado vira risco de glosa."
        ),
    )
    @action(detail=True, methods=["post"], url_path="concluir")
    def concluir(self, request, pk=None):
        demand = self._get_demand(pk)
        entrada = ConcluirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        demand = workflow_service.executar_transicao(
            demand, "concluida", ator=request.user, **entrada.validated_data,
        )
        return Response(DemandSerializer(demand).data)

    @extend_schema(
        filters=False, parameters=[PreviewDecisaoSerializer],
        responses={200: PreviewDecisaoRespostaSerializer, 400: ERRO_DE_DOMINIO},
    )
    @action(detail=True, methods=["get"], url_path="preview-decisao", pagination_class=None)
    def preview_decisao(self, request, pk=None):
        demand = self._get_demand(pk)
        query = PreviewDecisaoSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        solicitacao = get_object_or_404(
            DemandRequest, pk=query.validated_data["demand_request_id"], demanda=demand,
        )
        preview = approval_service.preview_impacto(
            solicitacao, query.validated_data["valor"], origem=query.validated_data["origem_allocation"],
        )
        return Response(preview)
