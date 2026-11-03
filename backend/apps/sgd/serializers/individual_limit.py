from rest_framework import serializers

from apps.core.models import User
from apps.sgp.models import SpendingLimit


class DemandIndividualLimitSerializer(serializers.ModelSerializer):
    """Contrato de `/sgd/limites-individuais/`, mantido enquanto o front migra para
    `/sgp/orcamento/limites/`."""

    solicitante = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all())
    saldo_disponivel = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = SpendingLimit
        fields = [
            "id", "solicitante", "rubrica", "rubrica_slug", "rubrica_nome",
            "valor_limite", "valor_comprometido", "valor_executado", "saldo_disponivel",
            "criado_por", "criado_em", "atualizado_em",
        ]
        read_only_fields = [
            "id", "valor_comprometido", "valor_executado", "criado_por", "criado_em", "atualizado_em",
        ]
        extra_kwargs = {"valor_limite": {"min_value": 0}}
        # A unicidade é por período e fica com o serviço, que responde a corrida no mesmo formato.
        validators = []

    def validate(self, attrs):
        if self.instance is None:
            return attrs
        # O comprometido é a soma das reservas desse solicitante nessa rubrica:
        # mover o limite para outro par deixaria as reservas sem limite.
        for campo, origem in (("solicitante", "user"), ("rubrica", "rubrica")):
            if origem in attrs and attrs[origem] != getattr(self.instance, origem):
                raise serializers.ValidationError({campo: "Não pode ser alterado; crie um novo limite."})
        novo = attrs.get("valor_limite")
        erro = novo is not None and self.instance.erro_de_reducao(novo)
        if erro:
            raise serializers.ValidationError({"valor_limite": erro})
        return attrs
