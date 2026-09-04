from rest_framework import serializers

from apps.core.models import State, Territory
from apps.sgp.models import BudgetAllocation, BudgetRubrica


class EstadoNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ["id", "sigla", "nome"]


class TerritorioNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = ["id", "nome"]


class BudgetRubricaNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetRubrica
        fields = ["id", "nome", "slug"]


class BudgetAllocationSerializer(serializers.ModelSerializer):
    """Leitura de uma alocação — usada na resposta das rotas de escrita e
    no `detalhamento` do orçamento por Meta."""

    rubrica = BudgetRubricaNestedSerializer(read_only=True)
    estado = EstadoNestedSerializer(read_only=True)
    territorio = TerritorioNestedSerializer(read_only=True)
    saldo_disponivel = serializers.SerializerMethodField()

    class Meta:
        model = BudgetAllocation
        fields = [
            "id", "meta", "rubrica", "nivel", "estado", "territorio",
            "valor_alocado", "valor_comprometido", "valor_executado",
            "reserva_ugp", "saldo_disponivel", "criado_por", "criado_em",
        ]
        read_only_fields = fields

    def get_saldo_disponivel(self, obj):
        return obj.valor_alocado - obj.valor_comprometido - obj.valor_executado


class BudgetRubricaOrcamentoSerializer(serializers.Serializer):
    """Uma linha da resposta de `GET .../orcamento/` — espelha o dict
    devolvido por `services.budget.orcamento_por_meta`."""

    rubrica = BudgetRubricaNestedSerializer()
    valor_aprovado = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_distribuido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_comprometido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=14, decimal_places=2)
    saldo_disponivel = serializers.DecimalField(max_digits=14, decimal_places=2)
    detalhamento = BudgetAllocationSerializer(many=True)


class BudgetAllocationCreateSerializer(serializers.Serializer):
    """Valida o payload de criação — a lógica de teto/concorrência fica no
    service (`services.budget.criar_alocacao`), não aqui."""

    rubrica_id = serializers.PrimaryKeyRelatedField(
        queryset=BudgetRubrica.objects.filter(ativo=True), source="rubrica",
    )
    nivel = serializers.ChoiceField(choices=BudgetAllocation.Nivel.choices)
    estado_id = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(), source="estado",
        required=False, allow_null=True, default=None,
    )
    territorio_id = serializers.PrimaryKeyRelatedField(
        queryset=Territory.objects.all(), source="territorio",
        required=False, allow_null=True, default=None,
    )
    valor_alocado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    reserva_ugp = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        nivel = attrs["nivel"]
        if nivel == BudgetAllocation.Nivel.NACIONAL and (attrs.get("estado") or attrs.get("territorio")):
            raise serializers.ValidationError(
                "Nível nacional não aceita estado nem território."
            )
        if nivel == BudgetAllocation.Nivel.ESTADUAL and not attrs.get("estado"):
            raise serializers.ValidationError({"estado_id": "Obrigatório para nível estadual."})
        if nivel == BudgetAllocation.Nivel.ESTADUAL and attrs.get("territorio"):
            raise serializers.ValidationError({"territorio_id": "Deve ser nulo para nível estadual."})
        if nivel == BudgetAllocation.Nivel.TERRITORIAL and not attrs.get("territorio"):
            raise serializers.ValidationError({"territorio_id": "Obrigatório para nível territorial."})
        if attrs.get("reserva_ugp") and nivel != BudgetAllocation.Nivel.NACIONAL:
            raise serializers.ValidationError({
                "reserva_ugp": "Reserva própria da UGP só é aplicável ao nível nacional."
            })
        return attrs


class BudgetAllocationUpdateSerializer(serializers.Serializer):
    valor_alocado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
