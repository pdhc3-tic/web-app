from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.core.permissions import (
    IsArticuladorEstadual,
    IsAuthenticatedActiveAccess,
    IsFGD,
    IsSuperAdmin,
    IsUGP,
)
from apps.sgd.services.approval import filtro_de_registro_da_demanda
from apps.sgp.models import GlosaRisk
from apps.sgp.serializers.glosa_risk import GlosaRiskQuerySerializer, GlosaRiskSerializer


@extend_schema(parameters=[GlosaRiskQuerySerializer])
class GlosaRiskListView(generics.ListAPIView):
    """GET /api/v1/sgp/glosa-riscos/ — por valor exposto; com `?demanda=`, em ordem cronológica.
    O Articulador vê o risco de quem vê a demanda e o das demandas do seu estado, que é o
    da demanda (território do solicitante) e não o da atividade."""

    permission_classes = [
        IsAuthenticatedActiveAccess, IsSuperAdmin | IsUGP | IsFGD | IsArticuladorEstadual,
    ]
    serializer_class = GlosaRiskSerializer
    queryset = GlosaRisk.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        consulta = GlosaRiskQuerySerializer(data=self.request.query_params)
        consulta.is_valid(raise_exception=True)
        filtros = consulta.validated_data

        riscos = GlosaRisk.objects.all()
        escopo = filtro_de_registro_da_demanda(self.request.user)
        if escopo is not None:
            riscos = riscos.filter(escopo)
        if "activity" in filtros:
            riscos = riscos.filter(activity_id=filtros["activity"])
        if "tipo" in filtros:
            riscos = riscos.filter(tipo_situacao=filtros["tipo"])
        if "severidade" in filtros:
            riscos = riscos.filter(severidade=filtros["severidade"])
        if "demanda" in filtros:
            return riscos.filter(demanda_id=str(filtros["demanda"])).order_by("detectado_em", "pk")
        return riscos.order_by("-valor_exposto", "-pk")
