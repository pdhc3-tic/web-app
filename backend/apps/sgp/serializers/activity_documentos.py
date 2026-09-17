from rest_framework import serializers

from apps.sgp.models import ActivityDocument


class ActivityDocumentSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = ActivityDocument
        fields = [
            "id", "activity", "tipo", "tipo_display", "descricao",
            "nome_original", "content_type", "tamanho_bytes",
            "data_documento", "ativo", "criado_em",
        ]
        read_only_fields = fields
