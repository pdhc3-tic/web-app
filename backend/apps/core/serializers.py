from rest_framework import serializers

from .models import Comunidade, Estado, Municipio, Territorio


class EstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estado
        fields = "__all__"


class TerritorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Territorio
        fields = "__all__"


class MunicipioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipio
        fields = "__all__"


class ComunidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comunidade
        fields = "__all__"
