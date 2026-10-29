from rest_framework import serializers

from apps.sgd.models.approval_step import ApprovalStep
from apps.sgp.models import BudgetAllocation


class ApprovalStepSerializer(serializers.ModelSerializer):
    """Uma linha do histórico da demanda (SGD-RF27)."""

    etapa_display = serializers.CharField(source="get_etapa_display", read_only=True)
    acao_display = serializers.CharField(source="get_acao_display", read_only=True)
    responsavel_id = serializers.IntegerField(allow_null=True, read_only=True)
    responsavel_nome = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalStep
        fields = [
            "id", "etapa", "etapa_display", "acao", "acao_display", "responsavel_id",
            "responsavel_nome", "justificativa", "excedente_autorizado", "criado_em",
        ]
        read_only_fields = fields

    def get_responsavel_nome(self, obj):
        return obj.responsavel.nome if obj.responsavel_id else None


def _por_id_de_solicitacao(valores: dict) -> dict:
    try:
        return {int(chave): valor for chave, valor in valores.items()}
    except ValueError:
        raise serializers.ValidationError("As chaves devem ser IDs de solicitação.")


class DevolverSerializer(serializers.Serializer):
    justificativa = serializers.CharField()


class AutorizarSerializer(serializers.Serializer):
    ajustes = serializers.DictField(
        child=serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0),
        required=False, default=dict,
        help_text="{demand_request_id: novo_valor} — omitido para autorizar sem ajuste.",
    )
    excedente_autorizado = serializers.BooleanField(required=False, default=False)
    origem_allocation = serializers.PrimaryKeyRelatedField(
        queryset=BudgetAllocation.objects.all(), required=False, allow_null=True, default=None,
        help_text=(
            "Com `excedente_autorizado`: alocação estadual ou nacional, da rubrica que excede, de onde "
            "sai o que passar do limite individual ou do pool territorial."
        ),
    )
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_ajustes(self, value):
        return _por_id_de_solicitacao(value)

    def validate(self, data):
        if data.get("excedente_autorizado"):
            erros = {}
            if not data.get("justificativa"):
                erros["justificativa"] = "Obrigatória para autorizar excedendo o limite individual."
            if data.get("origem_allocation") is None:
                erros["origem_allocation"] = "Informe a alocação estadual ou nacional que cobre o excedente."
            if erros:
                raise serializers.ValidationError(erros)
        elif data.get("origem_allocation") is not None:
            raise serializers.ValidationError({"origem_allocation": "Só é usada ao autorizar excedente."})
        return data


class RecusarSerializer(serializers.Serializer):
    justificativa = serializers.CharField()


class ConcluirSerializer(serializers.Serializer):
    valores_pagos = serializers.DictField(
        child=serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0),
        help_text=(
            "{demand_request_id: valor_pago} das solicitações ainda sem pagamento. Acima do "
            "autorizado, executa o autorizado e registra o excedente como risco de glosa."
        ),
    )

    def validate_valores_pagos(self, value):
        return _por_id_de_solicitacao(value)


class PreviewDecisaoSerializer(serializers.Serializer):
    demand_request_id = serializers.IntegerField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    origem_allocation = serializers.PrimaryKeyRelatedField(
        queryset=BudgetAllocation.objects.all(), required=False, allow_null=True, default=None,
        help_text="Simula a autorização com excedente coberto por esta alocação estadual ou nacional.",
    )


class CancelarSerializer(serializers.Serializer):
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")
    motivo = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        # `motivo` é o nome que o frontend atual envia.
        data["motivo"] = data["justificativa"] or data["motivo"]
        return data
