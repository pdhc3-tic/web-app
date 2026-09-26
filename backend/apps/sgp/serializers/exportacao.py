from rest_framework import serializers

from apps.sgp.models import ExportJob
from apps.sgp.serializers_workplan import WorkPlanExportQuerySerializer


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
    """Só a forma do pedido; os filtros de cada tipo são validados em
    `services.exportacao.validar_filtros`."""

    tipo = serializers.ChoiceField(choices=ExportJob.Tipo.choices)
    formato = serializers.ChoiceField(choices=ExportJob.Formato.choices)
    filtros = serializers.DictField(required=False, default=dict)
