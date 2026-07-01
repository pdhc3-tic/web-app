from rest_framework import serializers

from .models import Comunidade


class ComunidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comunidade
        fields = [
            'id', 'nome', 'municipio', 'lat', 'lng',
            'ativa', 'criada_em', 'criada_por',
        ]
        read_only_fields = ['id', 'criada_em', 'criada_por']
        validators = []

    def validate(self, attrs):
        nome = attrs.get('nome')
        municipio = attrs.get('municipio')
        if nome and municipio:
            municipio_pk = municipio.pk if hasattr(municipio, 'pk') else municipio
            qs = Comunidade.objects.filter(
                nome=nome, municipio_id=municipio_pk, ativa=True
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'nome': 'Já existe uma comunidade ativa com este nome neste município.',
                })
        return attrs
