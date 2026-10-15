from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.models.demand import Demand
from apps.sgd.serializers.consulta import CustoPorEntregaSerializer, PainelRubricaSerializer
from apps.sgd.services import consulta as consulta_service
from apps.sgd.services.approval import demand_visibility_scope


class _ConsultaGestaoView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def demandas_filtradas(self, request):
        consulta_service.exigir_perfil_de_gestao(request.user)
        qs = Demand.objects.all()
        scope = demand_visibility_scope(request.user)
        if scope is not None:
            qs = qs.filter(scope)
        return consulta_service.filtrar_demandas(qs.distinct(), request.query_params)


class PainelRubricasView(_ConsultaGestaoView):
    """Solicitado, autorizado, executado e disponível por rubrica (SGD-RF28)."""

    def get(self, request):
        demandas = self.demandas_filtradas(request)
        linhas = consulta_service.painel_por_rubrica(request.user, demandas, request.query_params)
        return Response(PainelRubricaSerializer(linhas, many=True).data)


class CustoPorAtividadeView(_ConsultaGestaoView):
    """Custo total por atividade e por entrega do Plano de Trabalho (SGD-RF29)."""

    def get(self, request):
        demandas = self.demandas_filtradas(request)
        linhas = consulta_service.custo_por_atividade(request.user, demandas)
        return Response(CustoPorEntregaSerializer(linhas, many=True).data)
