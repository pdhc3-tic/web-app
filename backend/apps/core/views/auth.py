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
from apps.core.throttling import (
    LoginRateThrottle,
    PasswordResetByEmailThrottle,
    PasswordResetByIPThrottle,
    PasswordResetConfirmThrottle,
    RefreshRateThrottle,
)
from apps.core.utils import get_client_ip
from setup.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    UserMeSerializer,
)

from apps.core.services.audit import log_audit
from setup.tasks import send_email_notification


logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def throttled(self, request, wait):
        ip = get_client_ip(request)
        email = request.data.get("email", "")
        security_logger.warning(
            "auth.login_rate_limited ip=%s path=%s",
            ip,
            request.path,
        )
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

            audit_user = None
            if not email or "@" not in email:
                motivo = LoginAttempt.MotivFalha.INVALID_FORMAT
            else:
                motivo = LoginAttempt.MotivFalha.INVALID_CREDENTIALS
                try:
                    audit_user = User.objects.get(email__iexact=email.strip())
                    if not audit_user.ativo:
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
    throttle_classes = [RefreshRateThrottle]

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
        except Exception as exc:
            security_logger.warning(
                "auth.refresh_failed ip=%s path=%s error=%s",
                get_client_ip(request),
                request.path,
                exc.__class__.__name__,
            )
            raise
        response.data["access_token"] = response.data.pop("access")
        response.data["refresh_token"] = response.data.pop("refresh")
        security_logger.info(
            "auth.refresh_success ip=%s path=%s",
            get_client_ip(request),
            request.path,
        )
        return response


class LogoutView(TokenBlacklistView):
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        audit_user = _get_user_from_refresh_token(request.data.get("refresh_token"))
        if audit_user is None and getattr(request.user, "is_authenticated", False):
            audit_user = request.user
        try:
            response = super().post(request, *args, **kwargs)
        except Exception as exc:
            security_logger.warning(
                "auth.logout_failed user_id=%s ip=%s path=%s error=%s",
                getattr(request.user, "pk", None),
                get_client_ip(request),
                request.path,
                exc.__class__.__name__,
            )
            raise

        security_logger.info(
            "auth.logout_success user_id=%s ip=%s path=%s",
            getattr(request.user, "pk", None),
            get_client_ip(request),
            request.path,
        )
        log_audit(
            user=audit_user,
            acao="auth.logout_success",
            modulo="core",
            entidade="User",
            entidade_id=getattr(audit_user, "pk", ""),
            valores_anteriores={},
            valores_novos={"status": "success"},
            request=request,
        )
        return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserMeSerializer(request.user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all(request):
    tokens = OutstandingToken.objects.filter(user=request.user)
    revoked_count = tokens.count()
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
    security_logger.info(
        "auth.logout_all_success user_id=%s ip=%s path=%s token_count=%s",
        request.user.pk,
        get_client_ip(request),
        request.path,
        revoked_count,
    )
    log_audit(
        user=request.user,
        acao="auth.logout_all_success",
        modulo="core",
        entidade="User",
        entidade_id=request.user.pk,
        valores_anteriores={},
        valores_novos={"revoked_count": revoked_count},
        request=request,
    )
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetByIPThrottle, PasswordResetByEmailThrottle])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = serializer.save()
    security_logger.info(
        "auth.password_reset_requested ip=%s path=%s",
        get_client_ip(request),
        request.path,
    )

    if result is not None:
        token_raw, user = result
        log_audit(
            user=user,
            acao="auth.password_reset_requested",
            modulo="core",
            entidade="User",
            entidade_id=user.pk,
            valores_anteriores={},
            valores_novos={"delivery": "email"},
            request=request,
        )
        link = f"{settings.FRONTEND_BASE_URL}/redefinir-senha#token={token_raw}"
        send_email_notification.delay(
            subject="Redefinição de senha — PDHC",
            message=f"Clique no link para redefinir sua senha:\n\n{link}\n\nO link expira em 24 horas.",
            recipient_list=[user.email],
        )
        security_logger.info(
            "auth.password_reset_email_enqueued user_id=%s ip=%s path=%s",
            user.pk,
            get_client_ip(request),
            request.path,
        )

    return Response(
        {"message": "Se o e-mail estiver cadastrado, um link foi enviado."},
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmThrottle])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(
        {"message": "Senha redefinida com sucesso."},
        status=status.HTTP_200_OK,
    )
