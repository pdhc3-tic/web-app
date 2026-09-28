from rest_framework import serializers


class DevolverSerializer(serializers.Serializer):
    justificativa = serializers.CharField()


class AutorizarSerializer(serializers.Serializer):
    ajustes = serializers.DictField(
        child=serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0),
        required=False, default=dict,
        help_text="{demand_request_id: novo_valor} — omitido para autorizar sem ajuste.",
    )
    excedente_autorizado = serializers.BooleanField(required=False, default=False)
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_ajustes(self, value):
        return {int(k): v for k, v in value.items()}

    def validate(self, data):
        if data.get("excedente_autorizado") and not data.get("justificativa"):
            raise serializers.ValidationError({
                "justificativa": "Obrigatória para autorizar excedendo o limite individual (RF16)."
            })
        return data


class RecusarSerializer(serializers.Serializer):
    justificativa = serializers.CharField()


class ConcluirSerializer(serializers.Serializer):
    valores_pagos = serializers.DictField(
        child=serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0),
        help_text="{demand_request_id: valor_pago}",
    )

    def validate_valores_pagos(self, value):
        return {int(k): v for k, v in value.items()}


class PreviewDecisaoSerializer(serializers.Serializer):
    demand_request_id = serializers.IntegerField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class AutorizarExcedenteSerializer(serializers.Serializer):
    demand_request_id = serializers.IntegerField()
    origem_allocation_id = serializers.IntegerField()
    valor_excedente = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    justificativa = serializers.CharField()
