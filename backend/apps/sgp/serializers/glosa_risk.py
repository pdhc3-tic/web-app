from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.sgp.models import GlosaRisk


class GlosaRiskSerializer(serializers.ModelSerializer):
    tipo = serializers.ChoiceField(source="tipo_situacao", choices=GlosaRisk.Tipo.choices, read_only=True)
    activity_id = serializers.IntegerField(read_only=True, allow_null=True)
    demanda_id = serializers.SerializerMethodField()
    demand_request_id = serializers.SerializerMethodField()
    criado_em = serializers.DateTimeField(source="detectado_em", read_only=True)

    class Meta:
        model = GlosaRisk
        fields = [
            "id", "tipo", "severidade", "valor_exposto", "activity_id", "demanda_id", "demand_request_id",
            "valor_autorizado", "valor_pago", "criado_em", "resolvido_em",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_demanda_id(self, obj):
        return int(obj.demanda_id)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_demand_request_id(self, obj):
        return int(obj.demand_request_id) if obj.demand_request_id else None


class GlosaRiskQuerySerializer(serializers.Serializer):
    activity = serializers.IntegerField(required=False)
    tipo = serializers.ChoiceField(choices=GlosaRisk.Tipo.choices, required=False)
    severidade = serializers.ChoiceField(choices=GlosaRisk.Severidade.choices, required=False)
    demanda = serializers.IntegerField(required=False)
