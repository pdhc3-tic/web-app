from rest_framework import serializers

from apps.sgd.models.arlo_import import ArloImport


class ArloDivergenciaSerializer(serializers.Serializer):
    demanda_id = serializers.IntegerField()
    demanda_titulo = serializers.CharField()
    solicitacao_id = serializers.IntegerField()
    valor_autorizado = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_pago = serializers.DecimalField(max_digits=14, decimal_places=2)
    diferenca = serializers.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Valor pago menos o autorizado: positivo acima do autorizado, negativo abaixo.",
    )
    risco_glosa = serializers.BooleanField(help_text="Pago acima do autorizado, registrado no risco de glosa.")


class ArloImportSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    operado_por_nome = serializers.CharField(source="operado_por.nome", read_only=True, default=None)
    divergencias = ArloDivergenciaSerializer(source="divergencias_json", many=True, read_only=True)

    class Meta:
        model = ArloImport
        fields = [
            "id", "tipo", "tipo_display", "status", "status_display", "arquivo_url", "nome_original",
            "operado_por", "operado_por_nome", "operado_em", "total_registros", "registros_ok", "erros_json",
            "divergencias", "mapeamento_snapshot",
        ]
        read_only_fields = fields
