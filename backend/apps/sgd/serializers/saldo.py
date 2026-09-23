from rest_framework import serializers


class SaldoConsultaQuerySerializer(serializers.Serializer):
    activity_id = serializers.IntegerField()
    rubrica = serializers.CharField(help_text="slug de BudgetRubrica")
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class TravaSerializer(serializers.Serializer):
    disponivel = serializers.BooleanField()
    saldo = serializers.DecimalField(max_digits=14, decimal_places=2)
    motivo_bloqueio = serializers.CharField(allow_null=True)
    acao_sugerida = serializers.CharField(allow_null=True)
    semaforo = serializers.CharField(allow_null=True)


class SaldoConsultaSerializer(serializers.Serializer):
    individual = TravaSerializer()
    territorial = TravaSerializer()
    disponivel = serializers.BooleanField()
    trava_bloqueada = serializers.CharField(allow_null=True)
