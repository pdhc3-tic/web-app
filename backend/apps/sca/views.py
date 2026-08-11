"""
Views do módulo SCA — endpoints de sync offline.

- POST /api/v1/sca/sync/push
- GET  /api/v1/sca/sync/pull
- GET  /api/v1/sca/sync/forms
- GET  /api/v1/sca/sync/status
- POST /api/v1/sca/auth/refresh
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.throttling import RefreshRateThrottle
from apps.sca import services
from apps.sca.serializers import PushBatchSerializer, ScaRefreshSerializer

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_device_id(request, body=None):
    device_id = request.headers.get("X-Device-Id") or request.query_params.get("device_id")
    if not device_id and body:
        device_id = body.get("device_id")
    return device_id


def _parse_since(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

class SyncPushView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def post(self, request):
        serializer = PushBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        device_id = _resolve_device_id(request, data)
        if not device_id and data["registros"]:
            device_id = data["registros"][0].get("device_id") or ""
        if not device_id:
            return Response(
                {"code": "DEVICE_ID_OBRIGATORIO", "message": "Informe o device_id no header X-Device-Id ou no corpo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device_meta = {
            "nome": request.data.get("dispositivo_nome") or request.data.get("nome") or "",
            "modelo": request.data.get("modelo") or "",
            "sistema_operacional": request.data.get("sistema_operacional") or "",
            "app_versao": request.data.get("app_versao") or "",
        }
        device = services.get_or_create_device(request.user, device_id, device_meta)
        processor = services.PushProcessor(request.user, device, device_id)
        resultados = processor.process(data["registros"])

        sucesso = sum(1 for r in resultados if r["status"] == "ok")
        return Response(
            {
                "resultados": resultados,
                "processados": len(resultados),
                "sucesso": sucesso,
                "erros": len(resultados) - sucesso,
            }
        )


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------

class SyncPullView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        since = _parse_since(request.query_params.get("since"))
        if request.query_params.get("since") and since is None:
            return Response(
                {"code": "SINCE_INVALIDO", "message": "Parâmetro 'since' inválido. Use ISO 8601 (ex: 2026-08-01T12:00:00-03:00)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device_id = _resolve_device_id(request)
        device = services.get_or_create_device(request.user, device_id)
        payload = services.build_pull(request.user, device, since)
        return Response(payload)


# ---------------------------------------------------------------------------
# Forms (fail-safe)
# ---------------------------------------------------------------------------

class SyncFormsView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        since = _parse_since(request.query_params.get("since"))
        if request.query_params.get("since") and since is None:
            return Response(
                {"code": "SINCE_INVALIDO", "message": "Parâmetro 'since' inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        formularios = services.get_published_forms(since, user=request.user)
        return Response(
            {
                "formularios": formularios,
                "server_time": timezone.now().isoformat(),
            }
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class SyncStatusView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        device_id = _resolve_device_id(request)
        device = services.get_or_create_device(request.user, device_id)

        ultimo_sync = device.ultimo_sync_em if device else None
        pendentes = services.count_pending_records(request.user, device)

        return Response(
            {
                "ultimo_sync_servidor": ultimo_sync.isoformat() if ultimo_sync else None,
                "registros_pendentes_servidor": pendentes,
                "acesso_revogado": bool(request.user.acesso_revogado),
            }
        )


# ---------------------------------------------------------------------------
# Auth refresh do SCA
# ---------------------------------------------------------------------------

class ScaAuthRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RefreshRateThrottle]

    def post(self, request):
        serializer = ScaRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            refresh = RefreshToken(data["refresh_token"])
        except TokenError:
            security_logger.warning("sca.refresh_invalid ip=%s path=%s", request.META.get("REMOTE_ADDR"), request.path)
            return Response(
                {"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token inválido ou expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if hasattr(refresh, "check_blacklist"):
            try:
                refresh.check_blacklist()
            except TokenError:
                security_logger.warning("sca.refresh_blacklisted ip=%s path=%s", request.META.get("REMOTE_ADDR"), request.path)
                return Response(
                    {"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token inválido ou expirado."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        User = get_user_model()
        try:
            user = User.objects.get(pk=refresh["user_id"], ativo=True)
        except User.DoesNotExist:
            return Response(
                {"code": "INVALID_REFRESH_TOKEN", "message": "Usuário não encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.acesso_revogado:
            security_logger.info("sca.refresh_access_revoked user_id=%s", user.pk)
            return Response(
                {"code": "ACCESS_REVOKED", "message": "Seu acesso foi revogado. Faça novo login com internet."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        device_id = data.get("device_id") or request.headers.get("X-Device-Id")
        device = services.get_or_create_device(user, device_id)

        if services.is_session_expired(user, device):
            return Response(
                {"code": "SESSION_EXPIRED", "message": "Sessão expirada por inatividade (30 dias sem sincronização). Faça novo login."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Rotação do refresh token (mesmo comportamento do SIMPLE_JWT padrão).
        if jwt_settings.ROTATE_REFRESH_TOKENS:
            if jwt_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except (AttributeError, TokenError):
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            new_refresh = str(refresh)
        else:
            new_refresh = data["refresh_token"]

        services.register_refresh(user, device)
        security_logger.info("sca.refresh_success user_id=%s device=%s", user.pk, device_id)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": new_refresh,
            }
        )
