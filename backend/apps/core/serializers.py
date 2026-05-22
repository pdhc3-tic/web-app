from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import Role, State, Territory, Municipality, Organization
from .models.notifications import Notification

User = get_user_model()

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
            'id', 'email', 'nome', 'role', 'ativo', 
            'ultimo_login', 'date_joined'
        ]
        read_only_fields = ['ultimo_login', 'date_joined']


class UserListSerializer(serializers.ModelSerializer):
    nome_completo = serializers.CharField(source="nome")
    perfis = serializers.SerializerMethodField()
    territorios = TerritorySerializer(many=True)
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
        if obj.role is None:
            return []
        return [RoleSerializer(obj.role).data]


class UserDetailSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    nome_completo = serializers.CharField(source="nome")
    perfis = serializers.SerializerMethodField()
    territorios = TerritorySerializer(many=True, read_only=True)
    perfil_id = serializers.PrimaryKeyRelatedField(
        source="role",
        queryset=Role.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    territorio_ids = serializers.PrimaryKeyRelatedField(
        source="territorios",
        queryset=Territory.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    password = serializers.CharField(write_only=True, required=False, allow_null=True)
    ultimo_login = serializers.DateTimeField(
        format="%Y-%m-%dT%H:%M:%SZ", allow_null=True, default=None, read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id", "nome_completo", "email", "perfis",
            "perfil_id", "territorios", "territorio_ids",
            "ativo", "ultimo_login", "telefone",
            "whatsapp", "foto_url", "password",
        ]
        read_only_fields = ["ultimo_login"]

    def get_perfis(self, obj):
        if obj.role is None:
            return []
        return [RoleSerializer(obj.role).data]

    def validate_email(self, value):
        value = value.lower().strip()
        instance = getattr(self, "instance", None)
        qs = User.objects.filter(email=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Já existe um usuário com este e-mail.")
        return value

    def create(self, validated_data):
        territorios = validated_data.pop("territorios", [])
        password = validated_data.pop("password", None)
        role = validated_data.pop("role", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        if role is not None:
            user.role = role
        user.save()
        if territorios:
            user.territorios.set(territorios)
        return user

    def update(self, instance, validated_data):
        territorios = validated_data.pop("territorios", None)
        password = validated_data.pop("password", None)
        role = validated_data.pop("role", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        if role is not None:
            instance.role = role

        instance.save()

        if territorios is not None:
            instance.territorios.set(territorios)

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

