from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.sgp.models import ExportJob
from apps.sgp.serializers_workplan import WorkPlanExportQuerySerializer
from apps.sgp.services.exportacao import validar_filtros


class AtividadesExportQuerySerializer(WorkPlanExportQuerySerializer):
    """Mesma validação de formato e período da exportação do PT, com Ação no
    lugar de Meta."""

    meta_id = None
    acao_id = serializers.IntegerField(min_value=1, required=False)


class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportJob
        fields = [
            "id", "tipo", "formato", "filtros", "status", "progresso", "erro",
            "total_registros", "nome_arquivo", "criado_em", "concluido_em", "expira_em",
        ]
        read_only_fields = fields


class ExportJobCreateSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=ExportJob.Tipo.choices)
    formato = serializers.ChoiceField(choices=ExportJob.Formato.choices)
    filtros = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        try:
            attrs["filtros"] = validar_filtros(attrs["tipo"], attrs["formato"], attrs["filtros"])
        except ValidationError as exc:
            raise serializers.ValidationError({"filtros": exc.detail})
        return attrs
