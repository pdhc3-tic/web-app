from datetime import date

from rest_framework import serializers

from apps.core.sensitive_fields import SensitiveFieldsSerializerMixin
from apps.sgp.models import MembroFamilia
from apps.sgp.services.access import upfs_acessiveis_ao_usuario
from apps.sgp.services.membro_rules import (
    CPFDuplicadoError,
    CPFInvalidoError,
    DataNascimentoFuturaError,
    SaudeInvalidaError,
    SeguridadeSocialInvalidaError,
    TitularDuplicadoError,
    validar_cpf,
    validar_data_nascimento,
    validar_saude,
    validar_seguridade_social,
    validar_titular_unico,
)


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
            "id", "upf", "nome_completo", "data_nascimento", "idade",
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
            try:
                validar_titular_unico(upf_id, membro_atual=self.instance)
            except TitularDuplicadoError:
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
        try:
            return validar_cpf(value, membro_atual=self.instance)
        except CPFInvalidoError as exc:
            raise serializers.ValidationError(exc.message)
        except CPFDuplicadoError as exc:
            duplicado = exc.duplicado
            upfs_visiveis = upfs_acessiveis_ao_usuario(self.context["request"].user)
            if duplicado.upf_id in upfs_visiveis.values_list("pk", flat=True):
                raise serializers.ValidationError(
                    "Já existe um membro cadastrado com este CPF: "
                    f"{duplicado.nome_completo} (UPF {duplicado.upf_id})"
                )
            raise serializers.ValidationError(
                "Já existe um membro cadastrado com este CPF"
            )

    def validate_data_nascimento(self, value):
        try:
            return validar_data_nascimento(value)
        except DataNascimentoFuturaError as exc:
            raise serializers.ValidationError(exc.message)

    def validate_saude(self, value):
        try:
            return validar_saude(value)
        except SaudeInvalidaError as exc:
            raise serializers.ValidationError(exc.message)

    def validate_seguridade_social(self, value):
        try:
            return validar_seguridade_social(value)
        except SeguridadeSocialInvalidaError as exc:
            raise serializers.ValidationError(exc.message)


class MembroExportQuerySerializer(serializers.Serializer):
    """Filtros aceitos por `GET /api/v1/sgp/membros/exportar/` (Issue #186)."""

    territorio_id = serializers.IntegerField(required=False, min_value=1)
    municipio = serializers.IntegerField(
        required=False, min_value=1, source="municipio_id"
    )
    projeto = serializers.IntegerField(
        required=False, min_value=1, source="projeto_id"
    )
