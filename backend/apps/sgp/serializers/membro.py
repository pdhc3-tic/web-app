from datetime import date

from rest_framework import serializers

from apps.core.sensitive_fields import SensitiveFieldsSerializerMixin
from apps.sgp.constants import SAUDE_CHOICES
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.validators import validate_cpf


class MembroListSerializer(SensitiveFieldsSerializerMixin, serializers.ModelSerializer):
    idade = serializers.SerializerMethodField()
    grau_parentesco_display = serializers.CharField(
        source="get_grau_parentesco_display", read_only=True
    )
    genero_display = serializers.CharField(
        source="get_genero_display", read_only=True
    )
    cor_raca_display = serializers.CharField(
        source="get_cor_raca_display", read_only=True
    )

    sensitive_fields = {
        "saude": ("saude",),
        "cor_raca": ("cor_raca", "cor_raca_display"),
    }

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome_completo", "data_nascimento", "idade",
            "grau_parentesco", "grau_parentesco_display", "cpf",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display", "saude",
            "criado_em",
        ]

    def get_idade(self, obj):
        if obj.data_nascimento:
            today = date.today()
            return (
                today.year - obj.data_nascimento.year
                - ((today.month, today.day) < (obj.data_nascimento.month, obj.data_nascimento.day))
            )
        return None


class MembroDetailSerializer(SensitiveFieldsSerializerMixin, serializers.ModelSerializer):
    idade = serializers.SerializerMethodField()
    grau_parentesco_display = serializers.CharField(
        source="get_grau_parentesco_display", read_only=True
    )
    genero_display = serializers.CharField(
        source="get_genero_display", read_only=True
    )
    cor_raca_display = serializers.CharField(
        source="get_cor_raca_display", read_only=True
    )
    escolaridade_display = serializers.CharField(
        source="get_escolaridade_display", read_only=True
    )
    cpf = serializers.CharField(
        max_length=14, required=False, allow_blank=True
    )

    sensitive_fields = {
        "saude": ("saude",),
        "cor_raca": ("cor_raca", "cor_raca_display"),
    }

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "upf", "nome_completo", "data_nascimento", "idade",
            "cpf", "rg", "nis", "caf", "grau_parentesco",
            "grau_parentesco_display",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
            "escola", "seguridade_social", "saude",
            "escolaridade", "escolaridade_display",
            "criado_por", "criado_em", "atualizado_em",
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
        ]
        validators = []
        read_only_fields = [
            "criado_em", "atualizado_em", "criado_por", "upf",
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
        ]

    def validate_grau_parentesco(self, value):
        if value == "titular":
            upf_id = self.instance.upf_id if self.instance else None
            if not upf_id:
                view_upf_id = self.context.get("view").kwargs.get("upf_pk") if self.context.get("view") else None
                if view_upf_id:
                    upf_id = view_upf_id
            if upf_id:
                upf = UPF.objects.filter(pk=upf_id).first()
                if upf and upf.titular_id:
                    if not self.instance or upf.titular_id != self.instance.pk:
                        raise serializers.ValidationError(
                            "Já existe um titular cadastrado para esta UPF"
                        )
        return value

    def get_idade(self, obj):
        if obj.data_nascimento:
            today = date.today()
            return (
                today.year - obj.data_nascimento.year
                - ((today.month, today.day) < (obj.data_nascimento.month, obj.data_nascimento.day))
            )
        return None

    def validate_cpf(self, value):
        if not value:
            return ""
        value = validate_cpf(value)
        qs = MembroFamilia.objects.filter(cpf=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        duplicado = qs.first()
        if duplicado:
            user = self.context["request"].user
            from apps.sgp.views import upfs_acessiveis_ao_usuario
            upfs_visiveis = upfs_acessiveis_ao_usuario(user)
            if duplicado.upf_id in upfs_visiveis.values_list("pk", flat=True):
                raise serializers.ValidationError(
                    "Já existe um membro cadastrado com este CPF: "
                    f"{duplicado.nome_completo} (UPF {duplicado.upf_id})"
                )
            raise serializers.ValidationError(
                "Já existe um membro cadastrado com este CPF"
            )
        return value

    def validate_data_nascimento(self, value):
        if value and value > date.today():
            raise serializers.ValidationError(
                "Data de nascimento não pode ser uma data futura"
            )
        return value

    def validate_saude(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Saúde deve ser uma lista de strings"
            )
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Condições de saúde não podem conter duplicidades.")
        for item in value:
            if item not in SAUDE_CHOICES:
                raise serializers.ValidationError(
                    f"'{item}' não é um valor válido para saúde. "
                    f"Valores permitidos: {', '.join(SAUDE_CHOICES)}"
                )
        if "nenhuma" in value and len(value) > 1:
            raise serializers.ValidationError(
                "A opção 'nenhuma' é mutuamente exclusiva com outras condições."
            )
        return value

    def validate_seguridade_social(self, value):
        from apps.sgp.constants import SEGURIDADE_SOCIAL_CHOICES
        if not isinstance(value, list):
            raise serializers.ValidationError("Seguridade social deve ser uma lista de strings.")
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Seguridade social não pode conter duplicidades.")
        for item in value:
            if item not in SEGURIDADE_SOCIAL_CHOICES:
                raise serializers.ValidationError(
                    f"'{item}' não é um valor válido para seguridade social. "
                    f"Valores permitidos: {', '.join(SEGURIDADE_SOCIAL_CHOICES)}"
                )
        if "nenhum" in value and len(value) > 1:
            raise serializers.ValidationError(
                "A opção 'nenhum' é mutuamente exclusiva com outros benefícios."
            )
        return value


class MembroExportQuerySerializer(serializers.Serializer):
    """Filtros aceitos por `GET /api/v1/sgp/membros/exportar/` (Issue #186)."""

    territorio_id = serializers.IntegerField(required=False, min_value=1)
    municipio = serializers.IntegerField(
        required=False, min_value=1, source="municipio_id"
    )
    projeto = serializers.IntegerField(
        required=False, min_value=1, source="projeto_id"
    )
