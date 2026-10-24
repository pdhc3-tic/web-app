from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import UsuarioRefSerializer
from apps.sgp.models import Activity
from apps.sgp.serializers.common import (
    MunicipioNestedSerializer,
    NestedSerializer,
    PlanoTrabalhoSerializer,
    plano_trabalho_da_acao,
)

# ---------------------------------------------------------------------------
# Calendar serializer — payload reduzido para grade de calendário
# ---------------------------------------------------------------------------

# Paleta semântica: status → cor HEX do design system PDHC
STATUS_COR_MAP: dict[str, str] = {
    "planejado":              "#6B7280",   # gray-500  — rascunho neutro
    "agendado":               "#3B82F6",   # blue-500  — confirmado
    "em_andamento":           "#F59E0B",   # amber-500 — em curso
    "concluido":              "#10B981",   # emerald-500 — sucesso
    "concluido_sem_evidencia":"#14B8A6",   # teal-500  — alerta leve
    "adiada":                 "#8B5CF6",   # violet-500 — reagendamento
    "nao_realizada":          "#EF4444",   # red-500   — falha
    "cancelada":              "#9CA3AF",   # gray-400  — encerrado
}


class ActivityCalendarioSerializer(serializers.ModelSerializer):
    """
    Payload mínimo para alimentar a grade de calendário (Dia/Semana/Mês).
    Todos os campos derivados são resolvidos a partir de select_related —
    zero queries adicionais por item.
    """
    tipo_atividade_display = serializers.CharField(
        source="get_tipo_atividade_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    atrasada = serializers.SerializerMethodField()
    cor = serializers.SerializerMethodField()
    tecnico_responsavel = serializers.SerializerMethodField()
    municipio = serializers.SerializerMethodField()
    comunidade = serializers.SerializerMethodField()
    plano_trabalho = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "titulo",
            "tipo_atividade",
            "tipo_atividade_display",
            "status",
            "status_display",
            "google_calendar_sync_status",
            "atrasada",
            "cor",
            "data_inicio",
            "data_fim",
            "tecnico_responsavel",
            "municipio",
            "comunidade",
            "plano_trabalho",
        ]
        read_only_fields = fields

    @extend_schema_field(PlanoTrabalhoSerializer)
    def get_plano_trabalho(self, obj) -> dict | None:
        return plano_trabalho_da_acao(obj.acao)

    def get_atrasada(self, obj) -> bool:
        return obj.esta_atrasada()

    def get_cor(self, obj) -> str:
        return STATUS_COR_MAP.get(obj.status, "#6B7280")

    @extend_schema_field(UsuarioRefSerializer)
    def get_tecnico_responsavel(self, obj) -> dict:
        u = obj.tecnico_responsavel
        return {"id": u.pk, "nome": u.nome}

    @extend_schema_field(MunicipioNestedSerializer)
    def get_municipio(self, obj) -> dict:
        return MunicipioNestedSerializer(obj.municipio).data

    @extend_schema_field(NestedSerializer(allow_null=True))
    def get_comunidade(self, obj) -> dict | None:
        if obj.comunidade_id:
            return {"id": obj.comunidade.pk, "nome": obj.comunidade.nome}
        return None
