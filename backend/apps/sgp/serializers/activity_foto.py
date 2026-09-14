from rest_framework import serializers

from apps.sgp.models import ActivityPhoto


class ActivityPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityPhoto
        fields = [
            "id", "activity", "arquivo_url", "legenda",
            "data_hora_captura", "latitude", "longitude",
            "ordem", "content_type", "tamanho_bytes",
            "ativa", "criado_em",
        ]
        read_only_fields = fields
