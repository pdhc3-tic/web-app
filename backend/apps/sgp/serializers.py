from datetime import date

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from apps.core.models import Municipality
from apps.sgp.constants import SAUDE_CHOICES
from apps.sgp.models import (
    Comunidade,
    Cultura,
    EspecieAnimal,
    MembroFamilia,
    Production,
    Projeto,
    UPF,
    UPFDocument,
)

from apps.sgp.validators import validate_cpf


class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = ["id", "nome", "descricao", "ativo", "criado_em"]
        read_only_fields = ["criado_em"]


class CulturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cultura
        fields = [
            "id",
            "nome",
            "nome_cientifico",
            "categoria",
            "ciclo",
            "ativa",
        ]


class EspecieAnimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspecieAnimal
        fields = ["id", "nome", "categoria", "ativa"]


class CatalogoProductionNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    categoria = serializers.CharField(read_only=True)


class ProductionSerializer(serializers.ModelSerializer):
    cultura = CatalogoProductionNestedSerializer(read_only=True)
    especie = CatalogoProductionNestedSerializer(read_only=True)
    cultura_id = serializers.PrimaryKeyRelatedField(
        queryset=Cultura.objects.filter(ativa=True),
        source="cultura",
        required=False,
        allow_null=True,
        write_only=True,
    )
    especie_id = serializers.PrimaryKeyRelatedField(
        queryset=EspecieAnimal.objects.filter(ativa=True),
        source="especie",
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Production
        fields = [
            "id",
            "upf",
            "tipo",
            "cultura",
            "cultura_id",
            "area_ha",
            "producao_estimada",
            "unidade_producao",
            "sementes_crioulas",
            "especie",
            "especie_id",
            "n_matrizes",
            "n_reprodutores",
            "n_jovens",
            "area_pastejo_ha",
            "sistema_criacao",
            "tipo_outra",
            "descricao_outra",
            "quantidade_produzida",
            "renda_estimada_mensal",
            "custo_anual",
            "observacoes",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "upf", "criado_em", "atualizado_em"]

    def validate(self, attrs):
        tipo = attrs.get("tipo", self.instance.tipo if self.instance else None)
        cultura = attrs.get("cultura", self.instance.cultura if self.instance else None)
        especie = attrs.get("especie", self.instance.especie if self.instance else None)
        tipo_outra = attrs.get(
            "tipo_outra",
            self.instance.tipo_outra if self.instance else None,
        )

        errors = {}
        if tipo == Production.TIPO_AGRICOLA:
            if not cultura:
                errors["cultura_id"] = "Cultura é obrigatória para produção agrícola."
            if especie:
                errors["especie_id"] = "Espécie deve ser nula para produção agrícola."
            if tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção agrícola."
        elif tipo == Production.TIPO_PECUARIA:
            if not especie:
                errors["especie_id"] = "Espécie é obrigatória para produção pecuária."
            if cultura:
                errors["cultura_id"] = "Cultura deve ser nula para produção pecuária."
            if tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção pecuária."
        elif tipo == Production.TIPO_OUTRA:
            if not tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade é obrigatório."
            if cultura:
                errors["cultura_id"] = "Cultura deve ser nula para outra atividade."
            if especie:
                errors["especie_id"] = "Espécie deve ser nula para outra atividade."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TitularNestedSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome_completo", "cpf", "rg", "data_nasc",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
            "escolaridade", "escolaridade_display",
            "nis",
            "idade",
        ]
        read_only_fields = ["id"]

    def get_idade(self, obj):
        if obj.data_nasc:
            today = date.today()
            return (
                today.year - obj.data_nasc.year
                - ((today.month, today.day) < (obj.data_nasc.month, obj.data_nasc.day))
            )
        return None


class UPFListSerializer(serializers.ModelSerializer):
    municipio = serializers.CharField(source="municipio.nome", read_only=True)
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


class NestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)


class UPFDocumentSerializer(serializers.ModelSerializer):
    criado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UPFDocument
        fields = [
            "id",
            "upf",
            "tipo",
            "descricao",
            "arquivo_key",
            "nome_original",
            "content_type",
            "tamanho_bytes",
            "data_documento",
            "criado_em",
            "criado_por",
        ]
        read_only_fields = [
            "id",
            "upf",
            "arquivo_key",
            "content_type",
            "tamanho_bytes",
            "criado_em",
            "criado_por",
        ]


class UPFDocumentCreateSerializer(serializers.Serializer):
    key = serializers.CharField()
    nome_original = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=UPFDocument.TIPO_CHOICES)
    descricao = serializers.CharField(required=False, allow_blank=True, default="")
    data_documento = serializers.DateField()


class UPFDetailSerializer(serializers.ModelSerializer):
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
    data_nasc = serializers.DateField(
        write_only=True, required=False, allow_null=True, default=None,
        source="_titular_data_nasc",
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
            "nome", "cpf", "rg", "data_nasc",
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
            "_titular_data_nasc": "data_nasc",
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
            "foto_url", "ativa",
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
        titular = MembroFamilia.objects.create(parentesco="titular", **titular_data)
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
        data["municipio"] = NestedSerializer(instance.municipio).data
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


class MembroListSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_completo", read_only=True)
    idade = serializers.SerializerMethodField()
    parentesco_display = serializers.CharField(
        source="get_parentesco_display", read_only=True
    )
    genero_display = serializers.CharField(
        source="get_genero_display", read_only=True
    )
    cor_raca_display = serializers.CharField(
        source="get_cor_raca_display", read_only=True
    )

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome", "data_nasc", "idade",
            "parentesco", "parentesco_display", "cpf",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
            "criado_em",
        ]

    def get_idade(self, obj):
        if obj.data_nasc:
            today = date.today()
            return (
                today.year - obj.data_nasc.year
                - ((today.month, today.day) < (obj.data_nasc.month, obj.data_nasc.day))
            )
        return None


class MembroDetailSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="nome_completo")
    idade = serializers.SerializerMethodField()
    parentesco_display = serializers.CharField(
        source="get_parentesco_display", read_only=True
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

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "upf", "nome", "data_nasc", "idade",
            "cpf", "rg", "nis", "caf", "parentesco",
            "parentesco_display",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
            "escola", "seguridade_social", "saude",
            "escolaridade", "escolaridade_display",
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
                upf = UPF.objects.filter(pk=upf_id).first()
                if upf and upf.titular_id:
                    if not self.instance or upf.titular_id != self.instance.pk:
                        raise serializers.ValidationError(
                            "Já existe um titular cadastrado para esta UPF"
                        )
        return value

    def get_idade(self, obj):
        if obj.data_nasc:
            today = date.today()
            return (
                today.year - obj.data_nasc.year
                - ((today.month, today.day) < (obj.data_nasc.month, obj.data_nasc.day))
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
