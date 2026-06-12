import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from apps.core.models.login_attempt import LoginAttempt
from apps.core.throttling import LoginRateThrottle
from apps.core.utils import get_client_ip
from setup.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    UserMeSerializer,
)
from setup.tasks import send_email_notification
from setup.throttles import PasswordResetByEmailThrottle, PasswordResetByIPThrottle


logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def throttled(self, request, wait):
        ip = get_client_ip(request)
        email = request.data.get("email", "")
        try:
            LoginAttempt.objects.create(
                email=email,
                ip=ip,
                sucesso=False,
                motivo_falha=LoginAttempt.MotivFalha.RATE_LIMITED,
            )
        except Exception as exc:
            logger.error("Erro ao gravar LoginAttempt (RATE_LIMITED): %s", exc)
        super().throttled(request, wait)

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        email = request.data.get("email", "")

        try:
            response = super().post(request, *args, **kwargs)
            response.data["access_token"] = response.data.pop("access")
            response.data["refresh_token"] = response.data.pop("refresh")

            try:
                LoginAttempt.objects.create(email=email, ip=ip, sucesso=True)
            except Exception as exc:
                logger.error("Erro ao gravar LoginAttempt: %s", exc)

            return response
        except Exception as exc:
            User = get_user_model()

            if not email or "@" not in email:
                motivo = LoginAttempt.MotivFalha.INVALID_FORMAT
            else:
                motivo = LoginAttempt.MotivFalha.INVALID_CREDENTIALS
                try:
                    user = User.objects.get(email=email)
                    if not user.ativo:
                        motivo = LoginAttempt.MotivFalha.INACTIVE_USER
                except User.DoesNotExist:
                    motivo = LoginAttempt.MotivFalha.INVALID_CREDENTIALS

            try:
                LoginAttempt.objects.create(email=email, ip=ip, sucesso=False, motivo_falha=motivo)
            except Exception as log_exc:
                logger.error("Erro ao gravar LoginAttempt: %s", log_exc)

            raise exc


class RefreshView(TokenRefreshView):
    serializer_class = RefreshSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        return response


class LogoutView(TokenBlacklistView):
    serializer_class = LogoutSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserMeSerializer(request.user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all(request):
    tokens = OutstandingToken.objects.filter(user=request.user)
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle, PasswordResetByIPThrottle, PasswordResetByEmailThrottle])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = serializer.save()

    if result is not None:
        token_raw, user = result
        link = f"{settings.FRONTEND_BASE_URL}/redefinir-senha?token={token_raw}"
        send_email_notification.delay(
            subject="Redefinição de senha — PDHC",
            message=f"Clique no link para redefinir sua senha:\n\n{link}\n\nO link expira em 24 horas.",
            recipient_list=[user.email],
        )

    return Response(
        {"message": "Se o e-mail estiver cadastrado, um link foi enviado."},
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(
        {"message": "Senha redefinida com sucesso."},
        status=status.HTTP_200_OK,
    )
