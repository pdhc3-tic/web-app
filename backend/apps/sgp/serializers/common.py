from rest_framework import serializers


class NestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)


class EstadoNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sigla = serializers.CharField(read_only=True)
    nome = serializers.CharField(read_only=True)


class MunicipioNestedSerializer(serializers.Serializer):
    """Município com o estado embutido — NestedSerializer genérico não dava
    conta disso e a UI ficava sem Estado (issue #226)."""
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    estado = EstadoNestedSerializer(source="state", read_only=True)
