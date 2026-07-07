import json

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import Role, State, Territory, Municipality, Organization
from .models.notifications import Notification
from .models.user_profile import UserProfile
from apps.core.models.audit_log import AuditLog
from .models.system_config import SystemConfig, TipoConfiguracao

User = get_user_model()


class SystemConfigSerializer(serializers.ModelSerializer):
    atualizado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SystemConfig
        fields = [
            "chave",
            "valor",
            "tipo",
            "descricao",
            "atualizado_por",
            "atualizado_em",
        ]
        read_only_fields = ["chave", "tipo", "atualizado_por", "atualizado_em"]

    def validate_valor(self, value):
        instance = getattr(self, "instance", None)
        if instance is None:
            return value

        tipo = instance.tipo

        if tipo == TipoConfiguracao.INTEGER:
            try:
                return str(int(value))
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Valor inválido para tipo INTEGER: '{value}' não é um número inteiro válido."
                )

        if tipo == TipoConfiguracao.BOOLEAN:
            if isinstance(value, bool):
                return str(value)
            if isinstance(value, str):
                normalized = value.lower().strip()
                if normalized in ("true", "false", "1", "0"):
                    return str(normalized in ("true", "1"))
            raise serializers.ValidationError(
                f"Valor inválido para tipo BOOLEAN: '{value}' não é um valor booleano válido."
            )

        if tipo == TipoConfiguracao.JSON:
            if isinstance(value, str):
                try:
                    json.loads(value)
                    return value
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        f"Valor inválido para tipo JSON: '{value}' não é um JSON válido."
                    )
            try:
                return json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Valor inválido para tipo JSON: não foi possível serializar."
                )

        return str(value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        tipo = instance.tipo
        valor_raw = data["valor"]

        if tipo == TipoConfiguracao.INTEGER:
            try:
                data["valor"] = int(valor_raw)
            except (ValueError, TypeError):
                pass
        elif tipo == TipoConfiguracao.BOOLEAN:
            data["valor"] = valor_raw == "True"
        elif tipo == TipoConfiguracao.JSON:
            try:
                data["valor"] = json.loads(valor_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return data


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'nome', 'slug', 'descricao', 'ativo', 'criado_em']
        read_only_fields = ['criado_em']

class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ['id', 'sigla', 'nome']

class TerritorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = ['id', 'nome', 'estados', 'articulador', 'ativo']

class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = [
            'id', 'nome', 'state', 'territory', 'codigo_ibge', 
            'area_km2', 'pop_total', 'pop_rural', 'idh', 
            'perc_extr_pobres', 'benef_programa_agri_familiar', 
            'estab_agri_familiar'
        ]

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'nome', 'ativo', 
            'ultimo_login',
        ]
        read_only_fields = ['ultimo_login']


class UserListSerializer(serializers.ModelSerializer):
    nome_completo = serializers.CharField(source="nome")
    perfis = serializers.SerializerMethodField()
    territorios = serializers.SerializerMethodField()
    ultimo_login = serializers.DateTimeField(
        format="%Y-%m-%dT%H:%M:%SZ", allow_null=True, default=None
    )

    class Meta:
        model = User
        fields = [
            "id", "nome_completo", "email", "perfis",
            "territorios", "ativo", "ultimo_login",
        ]

    def get_perfis(self, obj):
        profiles = obj.profiles.select_related("perfil").all()
        return [RoleSerializer(p.perfil).data for p in profiles]

    def get_territorios(self, obj):
        profile_territory_ids = list(
            obj.profiles.filter(territorio__isnull=False)
            .values_list("territorio_id", flat=True)
        )
        if profile_territory_ids:
            return TerritorySerializer(
                Territory.objects.filter(pk__in=profile_territory_ids), many=True
            ).data
        has_global = obj.profiles.filter(territorio__isnull=True).exists()
        if has_global:
            return TerritorySerializer(Territory.objects.all(), many=True).data
        return []


class PerfilInputSerializer(serializers.Serializer):
    perfil_id = serializers.IntegerField()
    territorio_id = serializers.IntegerField(allow_null=True, required=False, default=None)


class UserDetailSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    nome_completo = serializers.CharField(source="nome")
    perfis = serializers.SerializerMethodField()
    territorios = serializers.SerializerMethodField()
    perfis_input = PerfilInputSerializer(
        many=True,
        write_only=True,
        required=False,
    )
    password = serializers.CharField(write_only=True, required=False, allow_null=True)
    ultimo_login = serializers.DateTimeField(
        format="%Y-%m-%dT%H:%M:%SZ", allow_null=True, default=None, read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id", "nome_completo", "email", "perfis",
            "perfis_input", "territorios",
            "ativo", "ultimo_login", "telefone",
            "whatsapp", "foto_url", "password",
        ]
        read_only_fields = ["ultimo_login"]

    def get_perfis(self, obj):
        profiles = obj.profiles.select_related("perfil", "territorio").all()
        return [
            {
                "id": p.perfil_id,
                "slug": p.perfil.slug,
                "nome": p.perfil.nome,
                "territorio_id": p.territorio_id,
            }
            for p in profiles
        ]

    def get_territorios(self, obj):
        profile_territory_ids = list(
            obj.profiles.filter(territorio__isnull=False)
            .values_list("territorio_id", flat=True)
        )
        if profile_territory_ids:
            return TerritorySerializer(
                Territory.objects.filter(pk__in=profile_territory_ids), many=True
            ).data
        has_global = obj.profiles.filter(territorio__isnull=True).exists()
        if has_global:
            return TerritorySerializer(Territory.objects.all(), many=True).data
        return []

    def validate_email(self, value):
        value = value.lower().strip()
        instance = getattr(self, "instance", None)
        qs = User.objects.filter(email=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Já existe um usuário com este e-mail.")
        return value

    def _sync_profiles(self, user, perfis_data):
        user.profiles.all().delete()
        for item in perfis_data:
            UserProfile.objects.create(
                user=user,
                perfil_id=item["perfil_id"],
                territorio_id=item.get("territorio_id"),
            )

    def create(self, validated_data):
        perfis_data = validated_data.pop("perfis_input", None)
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if perfis_data:
            self._sync_profiles(user, perfis_data)
        return user

    def update(self, instance, validated_data):
        perfis_data = validated_data.pop("perfis_input", None)
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        if perfis_data is not None:
            self._sync_profiles(instance, perfis_data)

        return instance


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "tipo",
            "titulo",
            "mensagem",
            "link",
            "modulo_origem",
            "evento",
            "enviado_em",
            "lido_em",
            "status",
            "tentativas",
        ]
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    cnpj = serializers.CharField(
        validators=[
            UniqueValidator(
                queryset=Organization.objects.all(),
                message="Já existe uma organização cadastrada com este CNPJ",
            )
        ],
    )

    class Meta:
        model = Organization
        fields = [
            "id", "nome", "cnpj", "tipo", "municipio", "territorios",
            "contato", "email", "telefone", "ativa", "criado_em",
        ]
        read_only_fields = ["criado_em"]

    def validate_cnpj(self, value):
        from validate_docbr import CNPJ

        cnpj_validator = CNPJ()
        digits = "".join(c for c in value if c.isdigit())
        if not cnpj_validator.validate(digits):
            raise serializers.ValidationError("CNPJ inválido")
        return digits

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "acao",
            "modulo",
            "entidade",
            "entidade_id",
            "valores_anteriores",
            "valores_novos",
            "ip",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = fields
