from rest_framework import serializers

from apps.core.serializers import UsuarioRefSerializer
from apps.sgd.services.demand import ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA
from apps.sgp.models import Activity
from apps.sgp.serializers.activity import AcaoDaAtividadeSerializer
from apps.sgp.serializers.common import MunicipioNestedSerializer, NestedSerializer


class AtividadesElegiveisQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, default="", help_text="Trecho do título.")
    status = serializers.ListField(
        child=serializers.ChoiceField(choices=ACTIVITY_STATUS_ELEGIVEIS_NA_BUSCA), required=False, default=list,
        help_text="Repetível. Sem o parâmetro, as duas.",
    )


class AtividadeElegivelSerializer(serializers.ModelSerializer):
    """Mesmos nomes de campo da listagem de atividades do SGP."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    municipio = MunicipioNestedSerializer(read_only=True)
    tecnico_nome = serializers.CharField(source="tecnico_responsavel.nome", read_only=True, default=None)

    class Meta:
        model = Activity
        fields = [
            "id", "titulo", "status", "status_display", "data_inicio", "data_fim",
            "municipio", "tecnico_responsavel", "tecnico_nome",
        ]
        read_only_fields = fields


class AtividadeElegivelDetalheSerializer(serializers.ModelSerializer):
    """O que o formulário da demanda mostra da atividade escolhida, com os mesmos nomes e
    formatos do detalhe do SGP. O técnico sai sem e-mail: a atividade pode ser de outro
    território."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    municipio = MunicipioNestedSerializer(read_only=True)
    territorio = NestedSerializer(read_only=True, allow_null=True)
    comunidade = NestedSerializer(read_only=True, allow_null=True)
    tecnico_responsavel = UsuarioRefSerializer(read_only=True)
    acao = AcaoDaAtividadeSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id", "titulo", "status", "status_display", "data_inicio", "data_fim",
            "municipio", "territorio", "comunidade", "tecnico_responsavel", "acao",
        ]
        read_only_fields = fields
