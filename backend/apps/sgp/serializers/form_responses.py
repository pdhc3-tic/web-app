from django.utils import timezone
from rest_framework import serializers

from apps.sgp.models import FormResponse


class FormResponseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormResponse
        fields = [
            "id",
            "ufpa",
            "formulario_id",
            "formulario_nome",
            "formulario_versao",
            "contract_version",
            "resposta_id_origem",
            "data_preenchimento",
            "respondente",
            "status",
            "origem",
            "criado_em",
        ]
        read_only_fields = fields


class FormResponseDetailSerializer(FormResponseListSerializer):
    class Meta(FormResponseListSerializer.Meta):
        fields = [*FormResponseListSerializer.Meta.fields, "respostas_json"]


class FormResponseFormularioOptionSerializer(serializers.Serializer):
    """Opção do filtro de formulário: um formulário com resposta na UFPA.

    Distinto de `AvailableFormSerializer` — este cobre formulários já
    respondidos na UFPA corrente (para o filtro do histórico), não os
    formulários publicados disponíveis para novo preenchimento.
    """

    formulario_id = serializers.IntegerField()
    formulario_nome = serializers.CharField()
    formulario_versao = serializers.CharField()


class AvailableFormSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    versao = serializers.CharField()
    descricao = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    atualizado_em = serializers.DateTimeField()


class FormResponseReceiveSerializer(serializers.Serializer):
    SUPPORTED_CONTRACT_VERSION = "1.0"

    ufpa_id = serializers.IntegerField(min_value=1)
    formulario_id = serializers.IntegerField(min_value=1)
    formulario_nome = serializers.CharField(max_length=255)
    formulario_versao = serializers.CharField(max_length=50)
    respondente = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    status = serializers.ChoiceField(choices=FormResponse.Status.choices)
    respostas_json = serializers.JSONField()
    origem = serializers.ChoiceField(choices=FormResponse.Origem.choices)
    contract_version = serializers.CharField(max_length=20)
    resposta_id_origem = serializers.CharField(max_length=255)

    def validate_contract_version(self, value):
        if value != self.SUPPORTED_CONTRACT_VERSION:
            raise serializers.ValidationError(
                f"Versão de contrato não suportada: {value}."
            )
        return value

    def validate_ufpa_id(self, value):
        ufpa_queryset = self.context["ufpa_queryset"]
        ufpa = ufpa_queryset.filter(pk=value).first()
        if ufpa is None:
            raise serializers.ValidationError(
                "UFPA não encontrada ou sem permissão de acesso."
            )
        return ufpa

    def create(self, validated_data):
        ufpa = validated_data.pop("ufpa_id")
        response, created = FormResponse.objects.get_or_create(
            origem=validated_data["origem"],
            resposta_id_origem=validated_data["resposta_id_origem"],
            defaults={
                "ufpa": ufpa,
                "data_preenchimento": timezone.now(),
                **validated_data,
            },
        )
        response._was_created = created
        return response
