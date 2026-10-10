from rest_framework import serializers

from apps.core.models.audit_log import AuditLog
from apps.sgd.services.auditoria import ENTIDADE_DEMANDA


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
        return "status" if obj.entidade == ENTIDADE_DEMANDA else "saldo"

    def get_usuario(self, obj) -> dict | None:
        if obj.user is None:
            return None
        return {"id": obj.user.pk, "nome": obj.user.nome}
