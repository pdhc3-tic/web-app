from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer, TokenBlacklistSerializer

from rest_framework import serializers
from apps.core.models.user import User
from apps.core.models.role import Role
from apps.core.models.territory import Territory

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