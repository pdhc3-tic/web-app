from rest_framework import serializers

from apps.sgd.models.demand_request import DemandRequest

# Só diaria/passagem carregam CPF — a chave de campos_json que recebe o
# valor decriptado de volta na leitura varia entre elas.
_CHAVE_CPF_POR_TIPO = {"diaria": "beneficiario_cpf", "passagem": "passageiro_cpf"}


class DemandRequestSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = DemandRequest
        fields = [
            "id", "demanda", "tipo", "tipo_display", "rubrica", "rubrica_slug", "rubrica_nome",
            "campos_json", "valor_estimado", "valor_autorizado", "valor_pago", "ordem",
            "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "demanda", "rubrica", "valor_autorizado", "valor_pago", "criado_em", "atualizado_em"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        chave = _CHAVE_CPF_POR_TIPO.get(instance.tipo)
        if chave and instance.beneficiario_cpf:
            data["campos_json"] = {**data["campos_json"], chave: instance.beneficiario_cpf}
        return data


class DemandRequestCreateSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=DemandRequest._meta.get_field("tipo").choices)
    campos_json = serializers.JSONField()
    valor_estimado = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=0)
    ordem = serializers.IntegerField(required=False, default=0)
