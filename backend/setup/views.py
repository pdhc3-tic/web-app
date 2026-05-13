from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from .serializers import LoginSerializer, RefreshSerializer, LogoutSerializer, UserMeSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework import status
from django.conf import settings
from setup.tasks import send_email_notification
from setup.throttles import PasswordResetByIPThrottle, PasswordResetByEmailThrottle
from rest_framework.throttling import AnonRateThrottle

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        return response

class RefreshView(TokenRefreshView):
    serializer_class = RefreshSerializer

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
@throttle_classes([PasswordResetByIPThrottle, PasswordResetByEmailThrottle])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = serializer.save()

    # SÓ ENVIA E-MAIL SE ENCONTROU O USUÁRIO
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
def password_reset_confirm(request):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    serializer = PasswordResetConfirmSerializer(data=request.data, context={"ip": ip})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(
        {"message": "Senha redefinida com sucesso."},
        status=status.HTTP_200_OK,
    )