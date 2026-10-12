from rest_framework import serializers

from apps.sgd.models.approval_step import ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    etapa_display = serializers.CharField(source="get_etapa_display", read_only=True)
    acao_display = serializers.CharField(source="get_acao_display", read_only=True)
    # O responsável é SET_NULL: a etapa sobrevive à remoção do usuário.
    responsavel_nome = serializers.CharField(source="responsavel.nome", read_only=True, allow_null=True)

    class Meta:
        model = ApprovalStep
        fields = [
            "id", "etapa", "etapa_display", "acao", "acao_display", "responsavel_nome",
            "justificativa", "excedente_autorizado", "criado_em",
        ]
        read_only_fields = fields
