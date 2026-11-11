from rest_framework import serializers

from apps.sgp.models import Activity
from apps.sgp.serializers.common import MunicipioNestedSerializer


class AtividadeElegivelSerializer(serializers.ModelSerializer):
    """Mesmos nomes de campo da listagem de atividades do SGP."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    municipio = MunicipioNestedSerializer(read_only=True)
    tecnico_nome = serializers.CharField(source="tecnico_responsavel.nome", read_only=True, default=None)

    class Meta:
        model = Activity
        fields = [
            "id", "titulo", "status", "status_display", "data_inicio", "data_fim",
            "municipio", "tecnico_responsavel", "tecnico_nome",
        ]
        read_only_fields = fields
