from decimal import Decimal

from rest_framework import serializers

from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.serializers.tipo_solicitacao import SlugDeTipoField
from apps.sgd.services.approval import alerta_rubrica_fora_do_previsto
from apps.sgd.services.tipos_solicitacao import obter_validador


class DemandRequestSerializer(serializers.ModelSerializer):
    tipo = serializers.CharField(source="tipo_id", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)
    alerta_rubrica_fora_do_previsto = serializers.SerializerMethodField()

    class Meta:
        model = DemandRequest
        fields = [
            "id", "demanda", "tipo", "tipo_display", "rubrica", "rubrica_slug", "rubrica_nome",
            "campos_json", "valor_estimado", "valor_autorizado", "valor_pago", "ordem",
            "alerta_rubrica_fora_do_previsto", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "demanda", "rubrica", "valor_autorizado", "valor_pago", "criado_em", "atualizado_em"]

    def get_alerta_rubrica_fora_do_previsto(self, obj) -> bool:
        return alerta_rubrica_fora_do_previsto(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        validador = obter_validador(instance.tipo.validador)
        if validador and validador.chave_cpf and instance.beneficiario_cpf:
            data["campos_json"] = {**data["campos_json"], validador.chave_cpf: instance.beneficiario_cpf}
        return data


class DemandRequestCreateSerializer(serializers.Serializer):
    tipo = SlugDeTipoField()
    campos_json = serializers.JSONField()
    valor_estimado = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0.01"),
    )
    ordem = serializers.IntegerField(required=False, default=0)


class DemandRequestUpdateSerializer(serializers.Serializer):
    tipo = SlugDeTipoField(required=False)
    campos_json = serializers.JSONField(required=False)
    valor_estimado = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0.01"),
    )
