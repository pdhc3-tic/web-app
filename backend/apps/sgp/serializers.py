from datetime import date

from rest_framework import serializers

from apps.core.models import Municipality
from apps.sgp.constants import SAUDE_CHOICES
from apps.sgp.models import Comunidade, MembroFamilia, Projeto, UPF
from apps.sgp.validators import validate_cpf


class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = ["id", "nome", "descricao", "ativo", "criado_em"]
        read_only_fields = ["criado_em"]


class UPFListSerializer(serializers.ModelSerializer):
    municipio = serializers.CharField(
        source="municipio.nome", read_only=True
    )
    territorio = serializers.CharField(
        source="territorio.nome", read_only=True
    )
    cpf = serializers.SerializerMethodField()

    class Meta:
        model = UPF
        fields = [
            "id",
            "nome_titular",
            "cpf",
            "municipio",
            "territorio",
            "criado_em",
            "ativa",
        ]

    def get_cpf(self, obj):
        if obj.cpf:
            return f"{obj.cpf[:3]}.***.***-{obj.cpf[-2:]}"
        return ""


class NestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)


class UPFDetailSerializer(serializers.ModelSerializer):
    cpf = serializers.CharField(max_length=14)
    data_nasc = serializers.DateField(
        source="data_nascimento", required=False, allow_null=True
    )
    daf_caf = serializers.CharField(
        source="numero_dap", required=False, allow_blank=True
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all()
    )
    municipio = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.all()
    )
    territorio = serializers.PrimaryKeyRelatedField(read_only=True)
    comunidade = serializers.PrimaryKeyRelatedField(
        queryset=Comunidade.objects.all(),
        required=False,
        allow_null=True,
    )
    criado_por = serializers.StringRelatedField(read_only=True)
    membros = serializers.SerializerMethodField()

    class Meta:
        model = UPF
        fields = [
            "id", "projeto", "nome_titular", "apelido", "cpf", "rg",
            "data_nasc", "genero", "cor_raca", "estado_civil",
            "escolaridade",
            "nacionalidade", "naturalidade", "nome_mae", "nome_pai",
            "telefone", "whatsapp", "email", "internet", "dispositivo",
            "cep", "logradouro",
            "numero", "complemento", "bairro", "municipio",
            "territorio", "comunidade", "latitude", "longitude",
            "pct", "posse_terra", "area_terra_ha",
            "situacao_moradia", "tipo_moradia", "energia", "agua",
            "daf_caf", "nis", "seguridade_social",
            "foto_url", "criado_por", "ativa", "criado_em",
            "atualizado_em", "membros",
        ]
        validators = []
        read_only_fields = [
            "criado_em", "atualizado_em", "criado_por",
            "territorio", "membros",
        ]

    def get_membros(self, obj):
        membros = obj.membros.all()
        return MembroListSerializer(membros, many=True).data

    def validate_cpf(self, value):
        return validate_cpf(value)

    def validate(self, attrs):
        cpf = attrs.get("cpf")
        projeto = attrs.get("projeto")

        if cpf and projeto:
            qs = UPF.objects.filter(cpf=cpf, projeto=projeto, ativa=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "cpf": "Já existe uma UPF ativa cadastrada com este CPF neste projeto"
                    }
                )

        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["municipio"] = NestedSerializer(instance.municipio).data
        data["territorio"] = (
            NestedSerializer(instance.territorio).data
            if instance.territorio
            else None
        )
        data["projeto"] = NestedSerializer(instance.projeto).data
        data["comunidade"] = (
            NestedSerializer(instance.comunidade).data
            if instance.comunidade_id
            else None
        )
        return data


class MembroListSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_completo", read_only=True)
    idade = serializers.SerializerMethodField()
    parentesco_display = serializers.CharField(
        source="get_parentesco_display", read_only=True
    )

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome", "data_nasc", "idade",
            "parentesco", "parentesco_display", "cpf",
            "genero", "cor_raca",
            "criado_em",
        ]

    def get_idade(self, obj):
        if obj.data_nasc:
            today = date.today()
            return (
                today.year
                - obj.data_nasc.year
                - (
                    (today.month, today.day)
                    < (obj.data_nasc.month, obj.data_nasc.day)
                )
            )
        return None


class MembroDetailSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_completo")
    idade = serializers.SerializerMethodField()
    parentesco_display = serializers.CharField(
        source="get_parentesco_display", read_only=True
    )
    cpf = serializers.CharField(
        max_length=14, required=False, allow_blank=True
    )

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "upf", "nome", "data_nasc", "idade",
            "cpf", "rg", "nis", "caf", "parentesco",
            "parentesco_display", "genero", "cor_raca",
            "escola", "seguridade_social", "saude",
            "telefone", "email",
            "escolaridade", "profissao", "renda", "observacao",
            "criado_por", "criado_em", "atualizado_em",
        ]
        validators = []
        read_only_fields = [
            "criado_em", "atualizado_em", "criado_por", "upf",
        ]

    def validate_parentesco(self, value):
        if value == "titular":
            upf_id = self.instance.upf_id if self.instance else None
            if not upf_id:
                view_upf_id = self.context.get("view").kwargs.get("upf_pk") if self.context.get("view") else None
                if view_upf_id:
                    upf_id = view_upf_id
            if upf_id:
                qs = MembroFamilia.objects.filter(
                    upf_id=upf_id, parentesco="titular"
                )
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError(
                        "Já existe um titular cadastrado para esta UPF"
                    )
        return value

    def get_idade(self, obj):
        if obj.data_nasc:
            today = date.today()
            return (
                today.year
                - obj.data_nasc.year
                - (
                    (today.month, today.day)
                    < (obj.data_nasc.month, obj.data_nasc.day)
                )
            )
        return None

    def validate_cpf(self, value):
        if not value:
            return ""
        return validate_cpf(value)

    def validate_saude(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Saúde deve ser uma lista de strings"
            )
        for item in value:
            if item not in SAUDE_CHOICES:
                raise serializers.ValidationError(
                    f"'{item}' não é um valor válido para saúde. "
                    f"Valores permitidos: {', '.join(SAUDE_CHOICES)}"
                )
        return value


class HistoricoEntrySerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    campo = serializers.CharField(allow_null=True, read_only=True)
    valor_anterior = serializers.JSONField(allow_null=True, read_only=True)
    valor_novo = serializers.JSONField(allow_null=True, read_only=True)
    usuario = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(read_only=True)

    def get_usuario(self, obj):
        uid = obj.get("usuario_id")
        if uid is not None:
            return {"id": uid, "nome": obj.get("usuario_nome")}
        return None


class ComunidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comunidade
        fields = [
            'id', 'nome', 'municipio', 'lat', 'lng',
            'ativa', 'criada_em', 'criada_por',
        ]
        read_only_fields = ['id', 'criada_em', 'criada_por']
        validators = []

    def validate(self, attrs):
        nome = attrs.get('nome')
        municipio = attrs.get('municipio')
        if nome and municipio:
            municipio_pk = municipio.pk if hasattr(municipio, 'pk') else municipio
            qs = Comunidade.objects.filter(
                nome=nome, municipio_id=municipio_pk, ativa=True
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'nome': 'Já existe uma comunidade ativa com este nome neste município.',
                })
        return attrs
