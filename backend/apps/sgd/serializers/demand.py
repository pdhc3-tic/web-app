from rest_framework import serializers

from apps.sgd.models.demand import Demand
from apps.sgd.serializers.demand_request import DemandRequestSerializer
from apps.sgp.models.activity import TIPO_ATIVIDADE_CHOICES


class DemandContextoSerializer(serializers.Serializer):
    # Só expõe Ação/Meta — o SGP ainda não modela Submeta/Indicador (hierarquia
    # do documento tem 4 níveis, o código tem 2), então esses dois campos não
    # existem pra expor aqui.
    territorio_id = serializers.IntegerField(allow_null=True)
    territorio_nome = serializers.CharField(allow_null=True)
    municipio_id = serializers.IntegerField()
    municipio_nome = serializers.CharField()
    comunidade_id = serializers.IntegerField(allow_null=True)
    comunidade_nome = serializers.CharField(allow_null=True)
    data_prevista = serializers.DateTimeField(source="data_inicio")
    tecnico_id = serializers.IntegerField(source="tecnico_responsavel_id")
    tecnico_nome = serializers.CharField(source="tecnico_responsavel.nome")
    acao_numero = serializers.CharField(source="acao.numero")
    acao_descricao = serializers.CharField(source="acao.descricao")
    meta_numero = serializers.IntegerField(source="acao.meta.numero")
    meta_titulo = serializers.CharField(source="acao.meta.titulo")


def _contexto_da_activity(activity) -> dict:
    territory = activity.municipio.territory
    return {
        "territorio_id": territory.pk if territory else None,
        "territorio_nome": territory.nome if territory else None,
        "municipio_id": activity.municipio_id,
        "municipio_nome": activity.municipio.nome,
        "comunidade_id": activity.comunidade_id,
        "comunidade_nome": activity.comunidade.nome if activity.comunidade_id else None,
        "data_inicio": activity.data_inicio,
        "tecnico_responsavel_id": activity.tecnico_responsavel_id,
        "tecnico_responsavel": activity.tecnico_responsavel,
        "acao": activity.acao,
    }


class DemandSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    transicoes_permitidas = serializers.SerializerMethodField()
    valor_estimado_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    valor_autorizado_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    valor_pago_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    contexto = serializers.SerializerMethodField()
    solicitacoes = DemandRequestSerializer(many=True, read_only=True)

    class Meta:
        model = Demand
        fields = [
            "id", "titulo", "activity", "justificativa", "status", "status_display",
            "transicoes_permitidas", "solicitante", "despesa_posterior",
            "valor_estimado_total", "valor_autorizado_total", "valor_pago_total",
            "contexto", "solicitacoes", "criado_em", "atualizado_em",
        ]
        read_only_fields = [
            "id", "activity", "status", "solicitante", "despesa_posterior",
            "criado_em", "atualizado_em",
        ]

    def get_transicoes_permitidas(self, obj):
        return sorted(obj.get_transicoes_permitidas())

    def get_contexto(self, obj):
        return DemandContextoSerializer(_contexto_da_activity(obj.activity)).data


class DemandCreateSerializer(serializers.Serializer):
    titulo = serializers.CharField(max_length=255)
    justificativa = serializers.CharField(required=False, allow_blank=True, default="")

    activity_id = serializers.IntegerField(required=False)

    # Obrigatórios só se `activity_id` não vier — ver validate().
    activity_titulo = serializers.CharField(max_length=255, required=False)
    activity_tipo_atividade = serializers.ChoiceField(choices=TIPO_ATIVIDADE_CHOICES, required=False)
    activity_acao_id = serializers.IntegerField(required=False)
    activity_municipio_id = serializers.IntegerField(required=False)
    activity_data_prevista = serializers.DateTimeField(required=False)

    def validate(self, data):
        if data.get("activity_id"):
            return data
        obrigatorios = [
            "activity_titulo", "activity_tipo_atividade", "activity_acao_id",
            "activity_municipio_id", "activity_data_prevista",
        ]
        faltando = [c for c in obrigatorios if c not in data]
        if faltando:
            raise serializers.ValidationError(
                f"Sem 'activity_id', informe: {', '.join(faltando)}."
            )
        return data


class DemandUpdateSerializer(serializers.Serializer):
    titulo = serializers.CharField(max_length=255, required=False)
    justificativa = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if isinstance(self.initial_data, dict) and "activity_id" in self.initial_data:
            raise serializers.ValidationError({
                "activity_id": "Não pode ser alterado após a criação da demanda."
            })
        return data
