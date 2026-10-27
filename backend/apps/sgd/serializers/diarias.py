from rest_framework import serializers


class SimularDiariasQuerySerializer(serializers.Serializer):
    municipio_destino_id = serializers.IntegerField()
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()


class FaixaDestinoSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField()


class SimulacaoDiariasSerializer(serializers.Serializer):
    faixa_destino = FaixaDestinoSerializer()
    valor_por_diaria = serializers.DecimalField(max_digits=14, decimal_places=2)
    numero_diarias = serializers.DecimalField(max_digits=6, decimal_places=1)
    valor_total = serializers.DecimalField(max_digits=14, decimal_places=2)
