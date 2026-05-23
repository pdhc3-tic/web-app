from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import Role, State, Territory, Municipality, Organization
from .models.notifications import Notification
from apps.core.models.audit_log import AuditLog

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
            'ultimo_login',
        ]
        read_only_fields = ['ultimo_login']


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
