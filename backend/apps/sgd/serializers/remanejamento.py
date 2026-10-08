from rest_framework import serializers

from apps.sgp.models import BudgetAllocation, BudgetIncreaseRequest, BudgetRubrica
from apps.sgd.services.recurso_extra import DECISOES


class BudgetIncreaseRequestSerializer(serializers.ModelSerializer):
    solicitante_nome = serializers.CharField(source="user.nome", read_only=True)
    rubrica = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    transicoes_permitidas = serializers.SerializerMethodField()
    parecer_por_nome = serializers.CharField(source="parecer_por.nome", read_only=True, allow_null=True)
    decidido_por_nome = serializers.CharField(source="decidido_por.nome", read_only=True, allow_null=True)

    class Meta:
        model = BudgetIncreaseRequest
        fields = [
            "id", "user", "solicitante_nome", "rubrica", "rubrica_nome", "valor_solicitado",
            "valor_aprovado", "periodo_aplicacao", "activity", "demanda_id", "justificativa",
            "status", "status_display", "transicoes_permitidas",
            "parecer_articulador", "parecer_por", "parecer_por_nome",
            "justificativa_decisao", "decidido_por", "decidido_por_nome", "decidido_em",
            "criado_em", "atualizado_em",
        ]
        read_only_fields = fields

    def get_transicoes_permitidas(self, obj) -> list[str]:
        return sorted(obj.get_transicoes_permitidas())


class SolicitarRecursoExtraSerializer(serializers.Serializer):
    rubrica = serializers.SlugRelatedField(slug_field="slug", queryset=BudgetRubrica.objects.filter(ativo=True))
    valor_solicitado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    justificativa = serializers.CharField()
    periodo_aplicacao = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    submeter = serializers.BooleanField(required=False, default=True)


class AtualizarRemanejamentoSerializer(serializers.Serializer):
    valor_solicitado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    justificativa = serializers.CharField(required=False)
    periodo_aplicacao = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ParecerSerializer(serializers.Serializer):
    parecer = serializers.CharField()


class DevolverRemanejamentoSerializer(serializers.Serializer):
    justificativa = serializers.CharField()


class DecidirRemanejamentoSerializer(serializers.Serializer):
    decisao = serializers.ChoiceField(choices=sorted(DECISOES))
    valor_aprovado = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, required=False,
        help_text="Só na aprovação parcial.",
    )
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")
    origem_allocation = serializers.PrimaryKeyRelatedField(
        queryset=BudgetAllocation.objects.all(), required=False, allow_null=True, default=None,
        help_text="Alocação estadual ou nacional que cobre o que faltar no pool territorial.",
    )
