from datetime import date

from django.db import transaction
from rest_framework import serializers

from apps.core.models import Municipality
from apps.core.sensitive_fields import SensitiveFieldsSerializerMixin
from apps.sgp.models import Comunidade, MembroFamilia, Projeto, UPF
from apps.sgp.serializers.common import MunicipioNestedSerializer, NestedSerializer
from apps.sgp.serializers.membro import MembroListSerializer
from apps.sgp.validators import validate_cpf


class TitularNestedSerializer(SensitiveFieldsSerializerMixin, serializers.ModelSerializer):
    idade = serializers.SerializerMethodField()
    genero_display = serializers.CharField(
        source="get_genero_display", read_only=True
    )
    cor_raca_display = serializers.CharField(
        source="get_cor_raca_display", read_only=True
    )
    escolaridade_display = serializers.CharField(
        source="get_escolaridade_display", read_only=True
    )

    sensitive_fields = {
        "cor_raca": ("cor_raca", "cor_raca_display"),
    }

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome_completo", "cpf", "rg", "data_nascimento",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
            "escolaridade", "escolaridade_display",
            "nis",
            "idade",
        ]
        read_only_fields = ["id"]

    def get_idade(self, obj):
        if obj.data_nascimento:
            today = date.today()
            return (
                today.year - obj.data_nascimento.year
                - ((today.month, today.day) < (obj.data_nascimento.month, obj.data_nascimento.day))
            )
        return None


class UPFListSerializer(serializers.ModelSerializer):
    municipio = MunicipioNestedSerializer(read_only=True)
    territorio = serializers.CharField(source="territorio.nome", read_only=True)
    nome_titular = serializers.CharField(source="titular.nome_completo", read_only=True)
    cpf = serializers.SerializerMethodField()

    class Meta:
        model = UPF
        fields = [
            "id", "nome_titular", "cpf",
            "municipio", "territorio", "criado_em", "ativa",
            "foto_url",
        ]

    def get_cpf(self, obj):
        cpf = obj.titular.cpf
        if cpf:
            return f"{cpf[:3]}.***.***-{cpf[-2:]}"
        return ""


class UPFDetailSerializer(SensitiveFieldsSerializerMixin, serializers.ModelSerializer):
    sensitive_fields = {"cor_raca": ("cor_raca",)}

    # ── Titular (escrita) — nomes originais do formulário ──
    nome = serializers.CharField(
        write_only=True, required=True, source="_titular_nome",
    )
    cpf = serializers.CharField(
        write_only=True, required=True, source="_titular_cpf",
    )
    rg = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default="",
        source="_titular_rg",
    )
    data_nascimento = serializers.DateField(
        write_only=True, required=False, allow_null=True, default=None,
        source="_titular_data_nascimento",
    )
    genero = serializers.IntegerField(
        write_only=True, required=False, allow_null=True, default=None,
        source="_titular_genero",
    )
    cor_raca = serializers.IntegerField(
        write_only=True, required=False, allow_null=True, default=None,
        source="_titular_cor_raca",
    )
    escolaridade = serializers.IntegerField(
        write_only=True, required=False, allow_null=True, default=None,
        source="_titular_escolaridade",
    )
    nis = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default="",
        source="_titular_nis",
    )

    # ── Leitura (read_only) ──
    titular = TitularNestedSerializer(read_only=True)

    # ── UPF campos ──
    daf_caf = serializers.CharField(
        source="numero_dap", required=False, allow_blank=True,
    )
    projeto = serializers.PrimaryKeyRelatedField(queryset=Projeto.objects.all())
    municipio = serializers.PrimaryKeyRelatedField(queryset=Municipality.objects.all())
    territorio = serializers.PrimaryKeyRelatedField(read_only=True)
    comunidade = serializers.PrimaryKeyRelatedField(
        queryset=Comunidade.objects.all(), required=False, allow_null=True,
    )
    criado_por = serializers.StringRelatedField(read_only=True)
    membros = serializers.SerializerMethodField()

    class Meta:
        model = UPF
        fields = [
            "id", "projeto",
            "nome", "cpf", "rg", "data_nascimento",
            "genero", "cor_raca", "escolaridade",
            "nis",
            "titular",
            "apelido", "celular", "whatsapp", "internet", "dispositivo",
            "cep", "logradouro", "numero", "complemento", "bairro",
            "municipio", "territorio", "comunidade",
            "latitude", "longitude",
            "pct", "posse_terra", "area_terra_ha",
            "situacao_moradia", "tipo_moradia", "material_construcao",
            "num_comodos", "energia", "agua",
            "daf_caf", "seguridade_social",
            "foto_url", "criado_por", "ativa", "criado_em",
            "atualizado_em", "membros",
            # Sync SCA
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
        ]
        validators = []
        read_only_fields = [
            "criado_em", "atualizado_em", "criado_por",
            "territorio", "membros",
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
        ]

    def get_membros(self, obj):
        membros = obj.membros.all()
        return MembroListSerializer(membros, many=True, context=self.context).data

    def validate_cpf(self, value):
        return validate_cpf(value)

    def validate(self, attrs):
        cpf = attrs.get("_titular_cpf") or (
            self.instance.titular.cpf if self.instance else None
        )
        projeto = attrs.get("projeto")

        if cpf and projeto:
            projeto_pk = projeto.pk if hasattr(projeto, "pk") else projeto
            titular_ids = MembroFamilia.objects.filter(
                cpf=cpf, upf__projeto_id=projeto_pk, upf__ativa=True,
            ).exclude(
                upf=self.instance,
            ).values_list("pk", flat=True)
            if titular_ids:
                raise serializers.ValidationError(
                    {"cpf": "Já existe uma UPF ativa cadastrada com este CPF neste projeto"}
                )

        return attrs

    def _extract_titular_data(self, attrs):
        field_map = {
            "_titular_nome": "nome_completo",
            "_titular_cpf": "cpf",
            "_titular_rg": "rg",
            "_titular_data_nascimento": "data_nascimento",
            "_titular_genero": "genero",
            "_titular_cor_raca": "cor_raca",
            "_titular_escolaridade": "escolaridade",
            "_titular_nis": "nis",
        }
        data = {}
        for source_key, model_field in field_map.items():
            if source_key in attrs:
                data[model_field] = attrs[source_key]
        return data

    @transaction.atomic
    def _update_titular(self, upf):
        titular_data = self._extract_titular_data(self.validated_data)
        titular = upf.titular
        alterado = any(
            getattr(titular, key) != value for key, value in titular_data.items()
        )
        if alterado:
            titular.ultima_origem = "web"
        for key, value in titular_data.items():
            setattr(titular, key, value)
        titular.save()
        return titular

    def _upf_fields(self, attrs):
        upf_fields = {}
        upf_field_names = {
            "projeto", "apelido", "celular", "whatsapp", "internet",
            "dispositivo", "cep", "logradouro", "numero", "complemento",
            "bairro", "municipio", "territorio", "comunidade",
            "latitude", "longitude", "pct", "posse_terra", "area_terra_ha",
            "situacao_moradia", "tipo_moradia", "material_construcao",
            "num_comodos", "energia", "agua", "seguridade_social",
            "foto_url", "ativa", "ultima_origem",
        }
        daf_caf = attrs.pop("numero_dap", None)
        if daf_caf is not None:
            upf_fields["numero_dap"] = daf_caf
        for key in upf_field_names:
            if key in attrs:
                upf_fields[key] = attrs[key]
        return upf_fields

    def create(self, validated_data):
        upf_fields = self._upf_fields(validated_data)
        titular_data = self._extract_titular_data(validated_data)
        titular = MembroFamilia.objects.create(grau_parentesco="titular", **titular_data)
        upf = UPF.objects.create(titular=titular, **upf_fields)
        titular.upf = upf
        titular.save(update_fields=["upf"])
        upf.refresh_from_db()
        return upf

    def update(self, instance, validated_data):
        upf_fields = self._upf_fields(validated_data)
        for key, value in upf_fields.items():
            setattr(instance, key, value)
        instance.save()
        self._update_titular(instance)
        instance.refresh_from_db()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["municipio"] = MunicipioNestedSerializer(instance.municipio).data
        data["territorio"] = (
            NestedSerializer(instance.territorio).data
            if instance.territorio else None
        )
        data["projeto"] = NestedSerializer(instance.projeto).data
        data["comunidade"] = (
            NestedSerializer(instance.comunidade).data
            if instance.comunidade_id else None
        )
        return data


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
