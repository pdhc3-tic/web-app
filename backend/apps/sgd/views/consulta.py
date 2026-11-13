from django_filters import rest_framework as django_filters
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.filters import DemandFilter
from apps.sgd.models.demand import Demand
from apps.sgd.serializers.consulta import CustoPorEntregaSerializer, OpcaoUsuarioSerializer, PainelRubricaSerializer
from apps.sgd.serializers.erros import ERRO_DE_DOMINIO
from apps.sgd.services import consulta as consulta_service
from apps.sgd.services.approval import demand_visibility_scope


class _ConsultaGestaoView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]
    # Só para o drf-spectacular documentar os filtros da listagem, que
    # `filtrar_demandas` aplica aqui também.
    queryset = Demand.objects.none()
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = DemandFilter

    def demandas_filtradas(self, request):
        consulta_service.exigir_perfil_de_gestao(request.user)
        qs = Demand.objects.all()
        scope = demand_visibility_scope(request.user)
        if scope is not None:
            qs = qs.filter(scope)
        return consulta_service.filtrar_demandas(qs, request.query_params, request.user)


class PainelRubricasView(_ConsultaGestaoView):
    """Solicitado, autorizado, executado e disponível por rubrica (SGD-RF28)."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "estado", OpenApiTypes.STR,
                description="Sigla do estado: recorta os totais do orçamento, como `territorio` e `meta`.",
            ),
        ],
        responses={200: PainelRubricaSerializer(many=True), 400: ERRO_DE_DOMINIO},
    )
    def get(self, request):
        demandas = self.demandas_filtradas(request)
        linhas = consulta_service.painel_por_rubrica(request.user, demandas, request.query_params)
        return Response(PainelRubricaSerializer(linhas, many=True).data)


class CustoPorAtividadeView(_ConsultaGestaoView):
    """Custo total por atividade e por entrega do Plano de Trabalho (SGD-RF29)."""

    @extend_schema(responses={200: CustoPorEntregaSerializer(many=True), 400: ERRO_DE_DOMINIO})
    def get(self, request):
        demandas = self.demandas_filtradas(request)
        linhas = consulta_service.custo_por_atividade(request.user, demandas)
        return Response(CustoPorEntregaSerializer(linhas, many=True).data)


class OpcoesUsuariosView(APIView):
    """Listas dos filtros de solicitante e de responsável pela etapa atual do painel."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "papel", OpenApiTypes.STR, enum=list(consulta_service.PAPEIS_DE_USUARIO), required=True,
            ),
        ],
        responses={200: OpcaoUsuarioSerializer(many=True)},
    )
    def get(self, request):
        opcoes = consulta_service.opcoes_de_usuarios(request.user, request.query_params.get("papel", ""))
        return Response(OpcaoUsuarioSerializer(opcoes, many=True).data)
