from rest_framework import serializers

from apps.core.models.audit_log import AuditLog
from apps.sgd.services.auditoria import ENTIDADE_DEMANDA, ENTIDADE_MOVIMENTACAO_SALDO


class DemandAuditEntrySerializer(serializers.ModelSerializer):
    tipo = serializers.SerializerMethodField()
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "tipo", "acao", "usuario", "ip", "timestamp",
            "valores_anteriores", "valores_novos",
        ]
        read_only_fields = fields

    def get_tipo(self, obj) -> str:
        if obj.entidade == ENTIDADE_DEMANDA:
            return "status"
        if obj.entidade == ENTIDADE_MOVIMENTACAO_SALDO:
            return "saldo"
        return "recurso_extra"

    def to_representation(self, obj):
        dados = super().to_representation(obj)
        if not self.context.get("incluir_ip"):
            dados["ip"] = None
        return dados

    def get_usuario(self, obj) -> dict | None:
        if obj.user is None:
            return None
        return {"id": obj.user.pk, "nome": obj.user.nome}
