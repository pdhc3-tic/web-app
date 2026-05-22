import json

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import Role, State, Territory, Municipality, Organization
from .models.notifications import Notification
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
            'id', 'email', 'nome', 'role', 'ativo', 
            'ultimo_login', 'date_joined'
        ]
        read_only_fields = ['ultimo_login', 'date_joined']


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

