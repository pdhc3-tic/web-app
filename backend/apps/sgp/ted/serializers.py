from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import UsuarioRefSerializer
from apps.core.storage import get_storage
from apps.sgp.budget.serializers import BudgetRubricaNestedSerializer
from apps.sgp.models import TED, BudgetRubrica, TEDVersion, TEDVersionRubrica
from apps.sgp.ted.services import erro_no_documento

VALIDADE_DO_LINK_DO_DOCUMENTO = 300
TIPOS_DE_NOVA_VERSAO = [
    (TEDVersion.Tipo.ADITIVO.value, TEDVersion.Tipo.ADITIVO.label),
    (TEDVersion.Tipo.PRORROGACAO.value, TEDVersion.Tipo.PRORROGACAO.label),
]


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

class TEDVersaoRubricaEntradaSerializer(serializers.Serializer):
    rubrica = serializers.PrimaryKeyRelatedField(queryset=BudgetRubrica.objects.all())
    valor_aprovado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class TEDVersaoOriginalEntradaSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    vigencia_inicio = serializers.DateField()
    vigencia_fim = serializers.DateField()
    valor_global = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    rubricas = TEDVersaoRubricaEntradaSerializer(many=True, allow_empty=False)
    documento_key = serializers.CharField(
        help_text="Chave devolvida por `POST /sgp/ted/documentos/upload-url/` depois do envio do PDF.",
    )

    def validate_rubricas(self, value):
        ids = [item["rubrica"].pk for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Cada rubrica aparece uma vez só.")
        return value

    def validate(self, attrs):
        if attrs["vigencia_fim"] <= attrs["vigencia_inicio"]:
            raise serializers.ValidationError({"vigencia_fim": "O fim da vigência precisa ser depois do início."})
        return attrs


class TEDVersaoNovaEntradaSerializer(TEDVersaoOriginalEntradaSerializer):
    tipo = serializers.ChoiceField(choices=TIPOS_DE_NOVA_VERSAO)
    motivo = serializers.CharField()


class TEDCreateSerializer(serializers.Serializer):
    numero = serializers.CharField(max_length=100)
    participes = serializers.ListField(
        child=serializers.CharField(max_length=255), allow_empty=False,
    )
    objeto = serializers.CharField(required=False, allow_blank=True, default="")
    versao = TEDVersaoOriginalEntradaSerializer(help_text="Versão original do TED.")


CAMPOS_DA_VERSAO = ("valor_global", "vigencia_inicio", "vigencia_fim", "versao_vigente")


class TEDUpdateSerializer(serializers.Serializer):
    """Só a identificação. Valor global e vigência vêm da versão vigente: mandá-los
    aqui é recusado, para o cliente não achar que mudou o que não mudou."""

    numero = serializers.CharField(max_length=100, required=False)
    participes = serializers.ListField(
        child=serializers.CharField(max_length=255), allow_empty=False, required=False,
    )
    objeto = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        enviados = [campo for campo in CAMPOS_DA_VERSAO if campo in self.initial_data]
        if enviados:
            raise serializers.ValidationError({
                campo: "Muda só com o registro de uma nova versão do TED." for campo in enviados
            })
        return attrs


class TEDDocumentoUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        erro = erro_no_documento(attrs["content_type"], attrs["size"])
        if erro:
            campo, mensagem = erro
            raise serializers.ValidationError({campo: mensagem})
        return attrs


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

class TEDVersaoRubricaSerializer(serializers.ModelSerializer):
    rubrica = BudgetRubricaNestedSerializer(read_only=True)

    class Meta:
        model = TEDVersionRubrica
        fields = ["rubrica", "valor_aprovado"]
        read_only_fields = fields


class TEDVersaoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    registrado_por = UsuarioRefSerializer(read_only=True, allow_null=True)
    rubricas = TEDVersaoRubricaSerializer(many=True, read_only=True)

    class Meta:
        model = TEDVersion
        fields = [
            "id", "numero_versao", "tipo", "tipo_display", "motivo",
            "vigencia_inicio", "vigencia_fim", "valor_global", "rubricas",
            "registrado_por", "registrado_em",
        ]
        read_only_fields = fields


class TEDVersaoDetalheSerializer(TEDVersaoSerializer):
    documento_url = serializers.SerializerMethodField()

    class Meta(TEDVersaoSerializer.Meta):
        fields = TEDVersaoSerializer.Meta.fields + ["plano_snapshot", "documento_url"]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_documento_url(self, obj):
        url = get_storage().generate_presigned_get(obj.documento_key, VALIDADE_DO_LINK_DO_DOCUMENTO)
        request = self.context.get("request")
        if url.startswith("/") and request is not None:
            url = request.build_absolute_uri(url)
        return url


class TEDSerializer(serializers.ModelSerializer):
    versao_vigente = TEDVersaoSerializer(read_only=True, allow_null=True)

    class Meta:
        model = TED
        fields = [
            "id", "numero", "participes", "objeto", "valor_global",
            "vigencia_inicio", "vigencia_fim", "versao_vigente", "criado_em",
        ]
        read_only_fields = fields
