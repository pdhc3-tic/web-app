from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models.power_bi_token import PowerBIToken
from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.core.serializers import (
    PowerBITokenRegenerateSerializer,
    PowerBITokenStatusSerializer,
)
from apps.core.services.audit import log_audit
from apps.sgp.cache import get_power_bi_snapshot

POWER_BI_ENDPOINT_PATH = "/api/v1/sgp/plano-trabalho/powerbi/"
SNAPSHOT_ATRASO_LIMITE = timedelta(hours=1)


def _status_snapshot(atualizado_em_iso: str | None) -> str:
    if not atualizado_em_iso:
        return "sem_snapshot"
    atualizado_em = datetime.fromisoformat(atualizado_em_iso)
    if timezone.now() - atualizado_em > SNAPSHOT_ATRASO_LIMITE:
        return "atrasado"
    return "em_dia"


class PowerBITokenView(APIView):
    """GET /api/v1/admin/power-bi-token/ — status do token e do snapshot (Issue 143)."""

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]

    @extend_schema(responses=PowerBITokenStatusSerializer)
    def get(self, request):
        token = PowerBIToken.ativo_atual()
        snapshot = get_power_bi_snapshot() or {}
        atualizado_em = snapshot.get("atualizado_em")

        data = {
            "url_endpoint": POWER_BI_ENDPOINT_PATH,
            "token_mascarado": token.token_mascarado if token else None,
            "atualizado_em": atualizado_em,
            "status_snapshot": _status_snapshot(atualizado_em),
        }
        return Response(PowerBITokenStatusSerializer(data).data)


class PowerBITokenRegenerateView(APIView):
    """POST /api/v1/admin/power-bi-token/regenerar/ — invalida o token ativo e emite outro."""

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]

    @extend_schema(request=None, responses=PowerBITokenRegenerateSerializer)
    def post(self, request):
        token, token_raw = PowerBIToken.gerar(criado_por=request.user)

        # Nunca logar o segredo — nem em claro, nem o hash.
        log_audit(
            user=request.user,
            acao="power_bi_token.regenerated",
            modulo="core",
            entidade="PowerBIToken",
            entidade_id=token.pk,
            valores_anteriores={},
            valores_novos={"token_mascarado": token.token_mascarado},
            request=request,
        )

        data = {
            "token": token_raw,
            "token_mascarado": token.token_mascarado,
            "criado_em": token.criado_em,
        }
        return Response(PowerBITokenRegenerateSerializer(data).data)
