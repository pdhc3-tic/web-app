from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer, TokenBlacklistSerializer

from rest_framework import serializers
from apps.core.models.user import User
from apps.core.models.role import Role
from apps.core.models.territory import Territory

import hashlib
import secrets
import re
from datetime import timedelta
from django.utils import timezone
from apps.core.models.password_reset_token import PasswordResetToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from apps.core.models.audit_log import AuditLog
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class LoginSerializer(TokenObtainPairSerializer):
    senha = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("password")
         
    def validate(self, attrs):
        attrs["password"] = attrs.pop("senha")
        return super().validate(attrs)
    
class RefreshSerializer(TokenRefreshSerializer):
    refresh_token = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("refresh")

    def validate(self, attrs):
        attrs["refresh"] = attrs.pop("refresh_token")
        return super().validate(attrs)
    
class LogoutSerializer(TokenBlacklistSerializer):
    refresh_token = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("refresh", None)

    def validate(self, attrs):
        attrs["refresh"] = attrs.pop("refresh_token")
        return super().validate(attrs)
    
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "slug", "nome"]


class TerritorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = ["id", "nome", "estados"]


class UserMeSerializer(serializers.ModelSerializer):
    nome_completo = serializers.CharField(source="nome")
    perfis = serializers.SerializerMethodField()#RoleSerializer(source="role", many=False)
    territorios = TerritorySerializer(many=True)
    permissoes_resumo = serializers.SerializerMethodField()
    ultimo_login = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ")

    class Meta:
        model = User
        fields = [
            "id",
            "nome_completo",
            "email",
            "telefone",
            "whatsapp",
            "foto_url",
            "ultimo_login",
            "perfis",
            "territorios",
            "permissoes_resumo",
        ]

    def get_perfis(self, obj):
        if obj.role is None:
            return []
        return [RoleSerializer(obj.role).data]

    def get_permissoes_resumo(self, obj):
        return sorted(obj.get_all_permissions())
    
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()

    def save(self):
        email = self.validated_data["email"]

        try:
            user = User.objects.get(email=email, ativo=True)
        except User.DoesNotExist:
            return None

        # Gera token aleatório e salva hasheado
        token_raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()

        PasswordResetToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        return token_raw, user
    
class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    nova_senha = serializers.CharField(min_length=10)

    def validate_nova_senha(self, value):
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("A senha deve conter pelo menos uma letra maiúscula.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("A senha deve conter pelo menos um número.")
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        token_raw = attrs["token"]
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()

        try:
            reset_token = PasswordResetToken.objects.select_related("user").get(token_hash=token_hash)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError({"code": "INVALID_TOKEN"})

        if reset_token.used_at is not None:
            raise serializers.ValidationError({"code": "INVALID_TOKEN"})

        if reset_token.expires_at <= timezone.now():
            raise serializers.ValidationError({"code": "EXPIRED_TOKEN"})

        attrs["reset_token"] = reset_token
        return attrs

    def save(self):
        reset_token = self.validated_data["reset_token"]
        nova_senha = self.validated_data["nova_senha"]
        user = reset_token.user

        # Troca a senha
        user.set_password(nova_senha)
        user.save()

        # Marca o token como usado
        reset_token.used_at = timezone.now()
        reset_token.save()

        # Revoga todos os refresh tokens
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        # string vazia vira None (campo aceita null)
        ip = self.context.get("ip") or None  

        # Registra o evento no AuditLog
        AuditLog.objects.create(
            usuario=user,
            acao="password_reset",
            modulo="core",
            entidade="User",
            entidade_id=str(user.pk),
            valores_anteriores={},
            valores_novos={"email": user.email},
            ip=ip,
        )

        return user