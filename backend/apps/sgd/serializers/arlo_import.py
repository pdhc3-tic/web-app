from rest_framework import serializers

from apps.sgd.models.arlo_import import ArloImport


class ArloImportSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    operado_por_nome = serializers.CharField(source="operado_por.nome", read_only=True, default=None)

    class Meta:
        model = ArloImport
        fields = [
            "id", "tipo", "tipo_display", "status", "status_display", "arquivo_url", "nome_original",
            "operado_por", "operado_por_nome", "operado_em", "total_registros", "registros_ok", "erros_json",
        ]
        read_only_fields = fields
