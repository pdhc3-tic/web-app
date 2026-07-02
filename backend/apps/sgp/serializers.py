from rest_framework import serializers

from apps.core.models import Municipality
from apps.sgp.models import Projeto, UPF
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
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all()
    )
    municipio = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.all()
    )
    territorio = serializers.PrimaryKeyRelatedField(read_only=True)
    criado_por = serializers.StringRelatedField(read_only=True)
    membros = serializers.SerializerMethodField()

    class Meta:
        model = UPF
        fields = [
            "id",
            "projeto",
            "nome_titular",
            "cpf",
            "rg",
            "data_nascimento",
            "genero",
            "estado_civil",
            "nacionalidade",
            "naturalidade",
            "nome_mae",
            "nome_pai",
            "telefone",
            "celular",
            "email",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "municipio",
            "territorio",
            "latitude",
            "longitude",
            "situacao_moradia",
            "tipo_moradia",
            "numero_dap",
            "nis",
            "foto_url",
            "criado_por",
            "ativa",
            "criado_em",
            "atualizado_em",
            "membros",
        ]
        validators = []
        read_only_fields = [
            "criado_em",
            "atualizado_em",
            "criado_por",
            "territorio",
            "membros",
        ]

    def get_membros(self, obj):
        return []

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
        return data
