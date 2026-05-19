from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role, State, Territory, Municipality
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
