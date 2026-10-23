from rest_framework import serializers

from apps.core.utils import formatar_brl
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
        extra_kwargs = {"valor_limite": {"min_value": 0}}

    def validate(self, attrs):
        if self.instance is None:
            return attrs
        # O comprometido é a soma das reservas desse solicitante nessa rubrica:
        # mover o limite para outro par deixaria as reservas sem limite.
        for campo in ("solicitante", "rubrica"):
            if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                raise serializers.ValidationError({campo: "Não pode ser alterado; crie um novo limite."})
        # O limite não fica negativo. Depois de um excedente ele já pode estar
        # abaixo do comprometido: só a redução é barrada, o aumento ajuda.
        novo = attrs.get("valor_limite")
        minimo = self.instance.valor_comprometido + self.instance.valor_executado
        if novo is not None and novo < minimo and novo < self.instance.valor_limite:
            raise serializers.ValidationError({
                "valor_limite": f"Não pode ser reduzido abaixo do já comprometido e executado: {formatar_brl(minimo)}.",
            })
        return attrs
