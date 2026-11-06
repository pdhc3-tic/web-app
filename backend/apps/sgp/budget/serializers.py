from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.models import Role, State, Territory, User
from apps.sgp.budget.ledger import efeito_no_saldo
from apps.sgp.budget.limites import PERFIS_OPERACIONAIS
from apps.sgp.models import BudgetAlert, BudgetPool, BudgetRubrica, BudgetTransaction, SpendingLimit, WorkPlanMeta
from apps.sgp.serializers.common import EstadoNestedSerializer


class TerritorioNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = ["id", "nome", "estados"]


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
            "id", "pool", "spending_limit", "allocation", "activity", "tipo", "valor",
            "saldo_anterior", "saldo_posterior", "demanda_id", "demand_request_id",
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
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    justificativa = serializers.CharField()


FAIXAS_DO_SEMAFORO = ["verde", "amarelo", "vermelho"]


class ImpactoNoPoolSerializer(serializers.Serializer):
    saldo_antes = serializers.DecimalField(max_digits=14, decimal_places=2)
    saldo_depois = serializers.DecimalField(max_digits=14, decimal_places=2)
    percentual_antes = serializers.DecimalField(max_digits=8, decimal_places=2)
    percentual_depois = serializers.DecimalField(max_digits=8, decimal_places=2)
    percentual_execucao_antes = serializers.DecimalField(max_digits=8, decimal_places=2)
    percentual_execucao_depois = serializers.DecimalField(max_digits=8, decimal_places=2)
    faixa_antes = serializers.ChoiceField(choices=FAIXAS_DO_SEMAFORO)
    faixa_depois = serializers.ChoiceField(choices=FAIXAS_DO_SEMAFORO)


class SimulacaoRemanejamentoSerializer(serializers.Serializer):
    origem = ImpactoNoPoolSerializer()
    destino = ImpactoNoPoolSerializer()


class MeuSaldoSerializer(serializers.Serializer):
    rubrica = serializers.SlugField()
    rubrica_nome = serializers.CharField()
    limite = serializers.DecimalField(max_digits=14, decimal_places=2)
    comprometido = serializers.DecimalField(max_digits=14, decimal_places=2)
    executado = serializers.DecimalField(max_digits=14, decimal_places=2)
    disponivel = serializers.DecimalField(max_digits=14, decimal_places=2)
    semaforo = serializers.ChoiceField(choices=FAIXAS_DO_SEMAFORO)
    periodo_inicio = serializers.DateField()
    periodo_fim = serializers.DateField(allow_null=True)
    dias_restantes = serializers.IntegerField(allow_null=True)
    acumula_saldo = serializers.BooleanField()
    saldo_territorio = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)


class LinhaDoExtratoSerializer(BudgetTransactionSerializer):
    efeito = serializers.SerializerMethodField()
    periodo_inicio = serializers.DateField(source="spending_limit.periodo_inicio", read_only=True)
    periodo_fim = serializers.DateField(source="spending_limit.periodo_fim", read_only=True)

    class Meta(BudgetTransactionSerializer.Meta):
        fields = [*BudgetTransactionSerializer.Meta.fields, "efeito", "periodo_inicio", "periodo_fim"]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=2))
    def get_efeito(self, transacao):
        return f"{efeito_no_saldo(transacao.tipo, transacao.valor):.2f}"


class BudgetAlertSerializer(serializers.ModelSerializer):
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True, allow_null=True)

    class Meta:
        model = BudgetAlert
        fields = [
            "id", "tipo", "escopo", "referencia_id", "rubrica", "rubrica_nome", "faixa", "percentual_atingido",
            "criado_em", "alertado_em", "resolvido_em",
        ]
        read_only_fields = fields


class BudgetAlertQuerySerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=BudgetAlert.Tipo.choices, required=False)
    faixa = serializers.ChoiceField(choices=BudgetAlert.Faixa.choices, required=False)
    abertos = serializers.BooleanField(required=False, allow_null=True, default=None)


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
    semaforo = serializers.ChoiceField(choices=FAIXAS_DO_SEMAFORO)
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


class SpendingLimitSerializer(serializers.ModelSerializer):
    """Padrão por perfil ou linha individual. `herdado` diz se a linha veio do padrão do perfil
    ou é uma sobrescrita."""

    saldo_disponivel = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)
    perfil_slug = serializers.CharField(source="perfil.slug", read_only=True, allow_null=True)
    user_nome = serializers.CharField(source="user.nome", read_only=True, allow_null=True)

    class Meta:
        model = SpendingLimit
        fields = [
            "id", "escopo", "perfil", "perfil_slug", "user", "user_nome", "rubrica", "rubrica_slug", "rubrica_nome",
            "territorio", "valor_limite", "valor_comprometido", "valor_executado", "saldo_disponivel",
            "herdado", "justificativa", "periodo_inicio", "periodo_fim", "criado_por", "criado_em", "atualizado_em",
        ]
        read_only_fields = fields


class SpendingLimitCreateSerializer(serializers.Serializer):
    """Sem período, vale o período vigente. O padrão por perfil não tem fim: vale até ser alterado."""

    escopo = serializers.ChoiceField(choices=SpendingLimit.Escopo.choices)
    perfil = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(slug__in=PERFIS_OPERACIONAIS), required=False, allow_null=True,
        help_text="Só os perfis operacionais, que criam demandas: ADT/ACR e Articulador Estadual.",
    )
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    rubrica = serializers.PrimaryKeyRelatedField(queryset=BudgetRubrica.objects.filter(ativo=True))
    valor_limite = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")
    periodo_inicio = serializers.DateField(required=False)
    periodo_fim = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs["escopo"] == SpendingLimit.Escopo.PERFIL:
            if attrs.get("perfil") is None:
                raise serializers.ValidationError({"perfil": "Obrigatório no padrão por perfil."})
            if attrs.get("user") is not None:
                raise serializers.ValidationError({"user": "Só se aplica ao limite individual."})
            if attrs.get("periodo_fim") is not None:
                raise serializers.ValidationError({"periodo_fim": "O padrão por perfil vale até ser alterado."})
        else:
            if attrs.get("user") is None:
                raise serializers.ValidationError({"user": "Obrigatório no limite individual."})
            if attrs.get("perfil") is not None:
                raise serializers.ValidationError({"perfil": "Só se aplica ao padrão por perfil."})
        inicio, fim = attrs.get("periodo_inicio"), attrs.get("periodo_fim")
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError({"periodo_fim": "Não pode ser anterior ao início."})
        return attrs


class SpendingLimitUpdateSerializer(serializers.Serializer):
    valor_limite = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")


class SpendingLimitQuerySerializer(serializers.Serializer):
    data = serializers.DateField(required=False, help_text="Limites vigentes nesta data. Sem ela, hoje.")
    escopo = serializers.ChoiceField(choices=SpendingLimit.Escopo.choices, required=False)
    rubrica = serializers.SlugRelatedField(slug_field="slug", queryset=BudgetRubrica.objects.all(), required=False)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    perfil = serializers.SlugRelatedField(slug_field="slug", queryset=Role.objects.all(), required=False)
