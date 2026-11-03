from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.models import State, Territory
from apps.sgp.models import BudgetPool, BudgetRubrica, BudgetTransaction, WorkPlanMeta
from apps.sgp.serializers.common import EstadoNestedSerializer


class TerritorioNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = ["id", "nome"]


class BudgetRubricaNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetRubrica
        fields = ["id", "nome", "slug"]


class BudgetRubricaSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetRubrica
        fields = ["id", "slug", "nome", "ativo"]
        read_only_fields = fields


class BudgetPoolSerializer(serializers.ModelSerializer):
    """Leitura de um pool — usada na resposta das rotas de escrita e no
    `detalhamento` do orçamento por rubrica."""

    rubrica = BudgetRubricaNestedSerializer(read_only=True)
    estado = EstadoNestedSerializer(read_only=True, allow_null=True)
    territorio = TerritorioNestedSerializer(read_only=True, allow_null=True)
    saldo_disponivel = serializers.SerializerMethodField()

    class Meta:
        model = BudgetPool
        fields = [
            "id", "rubrica", "nivel", "estado", "territorio",
            "valor_alocado", "valor_comprometido", "valor_executado",
            "reserva_ugp", "saldo_disponivel", "criado_por", "criado_em",
        ]
        read_only_fields = fields

    # Decimal devolvido por método sai como número no JSON (o encoder do DRF
    # converte para float), e não como string, como os DecimalField.
    @extend_schema_field(OpenApiTypes.DOUBLE)
    def get_saldo_disponivel(self, obj):
        return obj.valor_alocado - obj.valor_comprometido - obj.valor_executado


class BudgetRubricaOrcamentoSerializer(serializers.Serializer):
    """Uma linha da resposta de `GET .../orcamento/` — espelha o dict
    devolvido por `budget.services.orcamento_por_rubrica`."""

    rubrica = BudgetRubricaNestedSerializer()
    valor_aprovado = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_distribuido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_comprometido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=14, decimal_places=2)
    saldo_disponivel = serializers.DecimalField(max_digits=14, decimal_places=2)
    detalhamento = BudgetPoolSerializer(many=True)


class BudgetPoolCreateSerializer(serializers.Serializer):
    """Valida o payload de criação — a lógica de teto/concorrência fica no
    service (`budget.services.criar_pool`), não aqui."""

    rubrica_id = serializers.PrimaryKeyRelatedField(
        queryset=BudgetRubrica.objects.filter(ativo=True), source="rubrica",
    )
    nivel = serializers.ChoiceField(choices=BudgetPool.Nivel.choices)
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
        if nivel == BudgetPool.Nivel.NACIONAL and (attrs.get("estado") or attrs.get("territorio")):
            raise serializers.ValidationError(
                "Nível nacional não aceita estado nem território."
            )
        if nivel == BudgetPool.Nivel.ESTADUAL and not attrs.get("estado"):
            raise serializers.ValidationError({"estado_id": "Obrigatório para nível estadual."})
        if nivel == BudgetPool.Nivel.ESTADUAL and attrs.get("territorio"):
            raise serializers.ValidationError({"territorio_id": "Deve ser nulo para nível estadual."})
        if nivel == BudgetPool.Nivel.TERRITORIAL and not attrs.get("territorio"):
            raise serializers.ValidationError({"territorio_id": "Obrigatório para nível territorial."})
        if attrs.get("reserva_ugp") and nivel != BudgetPool.Nivel.NACIONAL:
            raise serializers.ValidationError({
                "reserva_ugp": "Reserva própria da UGP só é aplicável ao nível nacional."
            })
        return attrs


class BudgetPoolUpdateSerializer(serializers.Serializer):
    valor_alocado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class BudgetTransactionSerializer(serializers.ModelSerializer):
    allocation = serializers.IntegerField(
        source="pool_id", read_only=True, help_text="Mesmo valor de `pool`, enquanto o front migra.",
    )

    class Meta:
        model = BudgetTransaction
        fields = [
            "id", "pool", "allocation", "activity", "tipo", "valor", "demanda_id",
            "justificativa", "criado_por", "criado_em",
        ]
        read_only_fields = fields


class SaldoConsultaQuerySerializer(serializers.Serializer):
    rubrica = serializers.SlugField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class SaldoConsultaSerializer(serializers.Serializer):
    """Resposta de `GET .../orcamento/saldo/` — espelha `SaldoCheck` mais o
    nível/localização resolvidos do perfil do usuário."""

    disponivel = serializers.BooleanField()
    saldo = serializers.DecimalField(max_digits=14, decimal_places=2)
    nivel = serializers.CharField()
    estado = EstadoNestedSerializer(allow_null=True)
    territorio = TerritorioNestedSerializer(allow_null=True)
    pool_id = serializers.IntegerField(allow_null=True)
    allocation_id = serializers.IntegerField(
        source="pool_id", allow_null=True, help_text="Mesmo valor de `pool_id`, enquanto o front migra.",
    )
    motivo_bloqueio = serializers.CharField(allow_null=True)


class RemanejamentoCreateSerializer(serializers.Serializer):
    origem_allocation = serializers.PrimaryKeyRelatedField(queryset=BudgetPool.objects.all())
    destino_allocation = serializers.PrimaryKeyRelatedField(queryset=BudgetPool.objects.all())
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    justificativa = serializers.CharField()


class LimiaresSemaforoSerializer(serializers.Serializer):
    amarelo = serializers.IntegerField()
    vermelho = serializers.IntegerField()


class BudgetPainelLinhaSerializer(serializers.Serializer):
    """Uma linha da matriz Rubrica × Nível: um pool, espelhando o dict devolvido por
    `budget.services.matriz_orcamento_para_usuario`."""

    id = serializers.IntegerField(help_text="Id do pool, o que a origem do excedente e a do recurso extra enviam.")
    rubrica = BudgetRubricaNestedSerializer()
    nivel = serializers.CharField()
    estado = EstadoNestedSerializer(allow_null=True)
    territorio = TerritorioNestedSerializer(allow_null=True)
    reserva_ugp = serializers.BooleanField()
    valor_aprovado = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_distribuido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_comprometido = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_executado_meta = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False,
        help_text="Só com `?meta=`: o executado deste pool nas atividades da Meta.",
    )
    saldo_disponivel = serializers.DecimalField(
        max_digits=14, decimal_places=2, help_text="Aprovado menos distribuído, comprometido e executado.",
    )
    saldo_pool = serializers.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Alocado menos comprometido e executado: o que o remanejamento aceita sair deste pool.",
    )
    semaforo = serializers.ChoiceField(choices=["verde", "amarelo", "vermelho"])
    alerta_80 = serializers.BooleanField()
    limiares_semaforo = LimiaresSemaforoSerializer()


class BudgetPainelQuerySerializer(serializers.Serializer):
    """Filtros de `GET .../orcamento/painel/` — `estado`/`territorio` fazem drill-down
    dentro do que o perfil do usuário permite (ver `resolver_nivel_painel`). `meta` não
    recorta o saldo, só acrescenta o executado dela."""

    meta = serializers.PrimaryKeyRelatedField(
        queryset=WorkPlanMeta.objects.all(), required=False,
    )
    rubrica = serializers.SlugRelatedField(
        slug_field="slug", queryset=BudgetRubrica.objects.filter(ativo=True), required=False,
    )
    estado = serializers.SlugRelatedField(
        slug_field="sigla", queryset=State.objects.all(), required=False,
    )
    territorio = serializers.PrimaryKeyRelatedField(
        queryset=Territory.objects.all(), required=False,
    )
    nivel = serializers.ChoiceField(choices=BudgetPool.Nivel.choices, required=False)
