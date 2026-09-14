from rest_framework import serializers

from apps.sgp.models import Tecnico


class TecnicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tecnico
        fields = ['id', 'user', 'territorio', 'osc', 'papel', 'ativo']
        read_only_fields = ['id']
