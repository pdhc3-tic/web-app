from rest_framework import serializers

from apps.sgd.models.individual_limit import DemandIndividualLimit


class DemandIndividualLimitSerializer(serializers.ModelSerializer):
    saldo_disponivel = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = DemandIndividualLimit
        fields = [
            "id", "solicitante", "rubrica", "rubrica_slug", "rubrica_nome",
            "valor_limite", "valor_comprometido", "valor_executado", "saldo_disponivel",
            "criado_por", "criado_em", "atualizado_em",
        ]
        read_only_fields = [
            "id", "valor_comprometido", "valor_executado", "criado_por", "criado_em", "atualizado_em",
        ]
