from rest_framework import serializers

from apps.sgp.models import UPFDocument


class UPFDocumentSerializer(serializers.ModelSerializer):
    criado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UPFDocument
        fields = [
            "id",
            "upf",
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
            "upf",
            "arquivo_key",
            "content_type",
            "tamanho_bytes",
            "criado_em",
            "criado_por",
        ]


class UPFDocumentCreateSerializer(serializers.Serializer):
    key = serializers.CharField()
    nome_original = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=UPFDocument.TIPO_CHOICES)
    descricao = serializers.CharField(required=False, allow_blank=True, default="")
    data_documento = serializers.DateField()
