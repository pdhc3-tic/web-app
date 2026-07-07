from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, RefreshSerializer, LogoutSerializer, UserMeSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework import status
from django.conf import settings
from setup.tasks import send_email_notification
import logging
from apps.core.models.login_attempt import LoginAttempt
from apps.core.services.audit import create_audit_log, get_client_ip as get_audit_client_ip
from apps.core.throttling import (
    LoginRateThrottle,
    PasswordResetByEmailThrottle,
    PasswordResetByIPThrottle,
    PasswordResetConfirmThrottle,
    RefreshRateThrottle,
)
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

def get_client_ip(request):
    return get_audit_client_ip(request) or ""


def _get_user_by_email(email):
    if not email or "@" not in email:
        return None
    User = get_user_model()
    try:
        return User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        return None


def _get_user_from_refresh_token(raw_token):
    if not raw_token:
        return None
    try:
        token = RefreshToken(raw_token)
    except TokenError:
        return None

    outstanding_token = OutstandingToken.objects.select_related("user").filter(
        jti=token.get("jti"),
    ).first()
    if outstanding_token is not None:
        return outstanding_token.user

    user_id = token.get("user_id")
    if user_id is None:
        return None
    User = get_user_model()
    return User.objects.filter(pk=user_id).first()

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def throttled(self, request, wait):
        """
        Sobrescreve o hook do DRF chamado antes de levantar Throttled.
        Grava o LoginAttempt com RATE_LIMITED de forma não-bloqueante —
        falha aqui nunca impede o 429 de ser retornado ao cliente.
        """
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
        audit_user = _get_user_by_email(email)
        create_audit_log(
            user=audit_user,
            acao="auth.login_rate_limited",
            entidade="User" if audit_user else "LoginAttempt",
            entidade_id=getattr(audit_user, "pk", ""),
            valores_novos={
                "reason": LoginAttempt.MotivFalha.RATE_LIMITED,
                "wait_seconds": int(wait or 0),
            },
            request=request,
        )
        super().throttled(request, wait)

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        email = request.data.get("email", "")

        try:
            response = super().post(request, *args, **kwargs)
            response.data["access_token"] = response.data.pop("access")
            response.data["refresh_token"] = response.data.pop("refresh")

            # Grava tentativa bem sucedida
            try:
                LoginAttempt.objects.create(email=email, ip=ip, sucesso=True)
            except Exception as exc:
                logger.error("Erro ao gravar LoginAttempt: %s", exc)

            security_logger.info(
                "auth.login_success ip=%s path=%s",
                ip,
                request.path,
            )
            audit_user = _get_user_by_email(email)
            create_audit_log(
                user=audit_user,
                acao="auth.login_success",
                entidade="User",
                entidade_id=getattr(audit_user, "pk", ""),
                valores_novos={"status": "success"},
                request=request,
            )

            return response
        except Exception as exc:
            # Identifica o motivo da falha            
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

            # Grava tentativa com falha
            try:
                LoginAttempt.objects.create(email=email, ip=ip, sucesso=False, motivo_falha=motivo)
            except Exception as exc:
                logger.error("Erro ao gravar LoginAttempt: %s", exc)

            security_logger.warning(
                "auth.login_failed ip=%s path=%s reason=%s",
                ip,
                request.path,
                motivo,
            )
            create_audit_log(
                user=audit_user,
                acao="auth.login_failed",
                entidade="User" if audit_user else "LoginAttempt",
                entidade_id=getattr(audit_user, "pk", ""),
                valores_novos={"reason": motivo},
                request=request,
            )

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
        create_audit_log(
            user=audit_user,
            acao="auth.logout_success",
            entidade="User",
            entidade_id=getattr(audit_user, "pk", ""),
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
    create_audit_log(
        user=request.user,
        acao="auth.logout_all_success",
        entidade="User",
        entidade_id=request.user.pk,
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

    # SÓ ENVIA E-MAIL SE ENCONTROU O USUÁRIO
    if result is not None:
        token_raw, user = result
        create_audit_log(
            user=user,
            acao="auth.password_reset_requested",
            entidade="User",
            entidade_id=user.pk,
            valores_novos={"delivery": "email"},
            request=request,
        )
        link = f"{settings.FRONTEND_BASE_URL}/redefinir-senha?token={token_raw}"
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
    ip = get_client_ip(request)
    serializer = PasswordResetConfirmSerializer(data=request.data, context={"ip": ip})
    try:
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
    except Exception as exc:
        security_logger.warning(
            "auth.password_reset_confirm_failed ip=%s path=%s error=%s",
            ip,
            request.path,
            exc.__class__.__name__,
        )
        raise
    security_logger.info(
        "auth.password_reset_completed user_id=%s ip=%s path=%s",
        user.pk,
        ip,
        request.path,
    )
    create_audit_log(
        user=user,
        acao="auth.password_reset_completed",
        entidade="User",
        entidade_id=user.pk,
        valores_novos={"status": "completed"},
        request=request,
        ip=ip,
    )
    return Response(
        {"message": "Senha redefinida com sucesso."},
        status=status.HTTP_200_OK,
    )
