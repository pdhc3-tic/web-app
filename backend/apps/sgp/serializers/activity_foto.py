from rest_framework import serializers

from apps.core.storage.serializers import SignedMediaUrlsMixin
from apps.sgp.models import ActivityPhoto


class ActivityPhotoSerializer(SignedMediaUrlsMixin, serializers.ModelSerializer):
    signed_media_url_fields = ("arquivo_url",)

    class Meta:
        model = ActivityPhoto
        fields = [
            "id", "activity", "arquivo_url", "legenda",
            "data_hora_captura", "latitude", "longitude",
            "ordem", "content_type", "tamanho_bytes",
            "ativo", "criado_em",
        ]
        read_only_fields = fields
