from rest_framework import serializers

from apps.sgp.models import Cultura, EspecieAnimal, Projeto


class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = ["id", "nome", "descricao", "ativo", "criado_em"]
        read_only_fields = ["criado_em"]


class CulturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cultura
        fields = [
            "id",
            "nome",
            "nome_cientifico",
            "categoria",
            "ciclo",
            "ativa",
        ]


class EspecieAnimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspecieAnimal
        fields = ["id", "nome", "categoria", "ativa"]


class CatalogoProductionNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    categoria = serializers.CharField(read_only=True)
