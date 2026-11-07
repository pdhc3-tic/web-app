from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.core.permissions import (
    IsArticuladorEstadual,
    IsAuthenticatedActiveAccess,
    IsFGD,
    IsSuperAdmin,
    IsUGP,
)
from apps.core.services.permissions import user_role_slugs, user_states
from apps.sgp.models import GlosaRisk
from apps.sgp.serializers.glosa_risk import GlosaRiskQuerySerializer, GlosaRiskSerializer

PERFIS_COM_VISAO_TOTAL = ("super-admin", "ugp", "fgd")


@extend_schema(parameters=[GlosaRiskQuerySerializer])
class GlosaRiskListView(generics.ListAPIView):
    """GET /api/v1/sgp/glosa-riscos/ — por valor exposto; com `?demanda=`, em ordem cronológica."""

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
        if not user_role_slugs(self.request.user, PERFIS_COM_VISAO_TOTAL):
            # Sem filtrar `ativo`: inativar a atividade não apaga o risco da despesa já feita.
            riscos = riscos.filter(activity__municipio__state__sigla__in=user_states(self.request.user))
        if "activity" in filtros:
            riscos = riscos.filter(activity_id=filtros["activity"])
        if "tipo" in filtros:
            riscos = riscos.filter(tipo_situacao=filtros["tipo"])
        if "severidade" in filtros:
            riscos = riscos.filter(severidade=filtros["severidade"])
        if "demanda" in filtros:
            return riscos.filter(demanda_id=str(filtros["demanda"])).order_by("detectado_em", "pk")
        return riscos.order_by("-valor_exposto", "-pk")
