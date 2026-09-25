from rest_framework import serializers

from apps.sgd.models.demand_document import DemandDocument


class DemandDocumentSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = DemandDocument
        fields = [
            "id", "demanda", "tipo", "tipo_display", "arquivo_url", "descricao", "fornecedor",
            "nome_original", "content_type", "tamanho_bytes", "enviado_por", "enviado_em",
        ]
        read_only_fields = fields
