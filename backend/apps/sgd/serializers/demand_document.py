from rest_framework import serializers

from apps.core.storage.serializers import SignedMediaUrlsMixin
from apps.sgd.models.demand_document import DemandDocument


class DemandDocumentSerializer(SignedMediaUrlsMixin, serializers.ModelSerializer):
    signed_media_url_fields = ("arquivo_url",)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = DemandDocument
        fields = [
            "id", "demanda", "tipo", "tipo_display", "arquivo_url", "descricao", "fornecedor",
            "nome_original", "content_type", "tamanho_bytes", "solicitacao", "campo", "enviado_por", "enviado_em",
        ]
        read_only_fields = fields
