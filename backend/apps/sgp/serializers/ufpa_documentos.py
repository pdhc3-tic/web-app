from rest_framework import serializers

from apps.sgp.models import UFPADocument


class UFPADocumentSerializer(serializers.ModelSerializer):
    criado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UFPADocument
        fields = [
            "id",
            "ufpa",
            "tipo",
            "descricao",
            "arquivo_key",
            "nome_original",
            "content_type",
            "tamanho_bytes",
            "data_documento",
            "criado_em",
            "criado_por",
        ]
        read_only_fields = [
            "id",
            "ufpa",
            "arquivo_key",
            "content_type",
            "tamanho_bytes",
            "criado_em",
            "criado_por",
        ]


class UFPADocumentCreateSerializer(serializers.Serializer):
    key = serializers.CharField()
    nome_original = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=UFPADocument.TIPO_CHOICES)
    descricao = serializers.CharField(required=False, allow_blank=True, default="")
    data_documento = serializers.DateField()
