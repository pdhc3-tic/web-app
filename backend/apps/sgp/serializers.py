from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.core.models import Municipality
from apps.sgp.constants import SAUDE_CHOICES
from apps.sgp.models import (
    Activity,
    Comunidade,
    Cultura,
    EspecieAnimal,
    FormResponse,
    MembroFamilia,
    Production,
    Projeto,
    UPF,
    UPFDocument,
    WorkPlanAcao,
)
from apps.sgp.models.activity import STATUS_TRANSITIONS, STATUS_TERMINAIS

from apps.core.services.permissions import user_territories
from apps.sgp.validators import validate_cpf


class FormResponseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormResponse
        fields = [
            "id",
            "upf",
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
    """Opção do filtro de formulário: um formulário com resposta na UPF.

    Distinto de `AvailableFormSerializer` — este cobre formulários já
    respondidos na UPF corrente (para o filtro do histórico), não os
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

    upf_id = serializers.IntegerField(min_value=1)
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

    def validate_upf_id(self, value):
        upf_queryset = self.context["upf_queryset"]
        upf = upf_queryset.filter(pk=value).first()
        if upf is None:
            raise serializers.ValidationError(
                "UPF não encontrada ou sem permissão de acesso."
            )
        return upf

    def create(self, validated_data):
        upf = validated_data.pop("upf_id")
        response, created = FormResponse.objects.get_or_create(
            origem=validated_data["origem"],
            resposta_id_origem=validated_data["resposta_id_origem"],
            defaults={
                "upf": upf,
                "data_preenchimento": timezone.now(),
                **validated_data,
            },
        )
        response._was_created = created
        return response


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

    class Meta:
        model = MembroFamilia
        fields = [
            "id", "nome_completo", "data_nascimento", "idade",
            "grau_parentesco", "grau_parentesco_display", "cpf",
            "genero", "genero_display",
            "cor_raca", "cor_raca_display",
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


class MembroDetailSerializer(serializers.ModelSerializer):
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


# ---------------------------------------------------------------------------
# Activity serializers
# ---------------------------------------------------------------------------

class ActivityListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listagem de atividades."""
    tipo_atividade_display = serializers.CharField(
        source="get_tipo_atividade_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    ambito_display = serializers.CharField(
        source="get_ambito_display", read_only=True
    )
    municipio_nome = serializers.CharField(
        source="municipio.nome", read_only=True
    )
    tecnico_nome = serializers.CharField(
        source="tecnico_responsavel.nome", read_only=True
    )
    total_participantes = serializers.SerializerMethodField()
    atrasada = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id", "titulo", "tipo_atividade", "tipo_atividade_display",
            "forma_atuacao", "ambito", "ambito_display",
            "municipio", "municipio_nome",
            "data_inicio", "data_fim",
            "status", "status_display",
            "tecnico_responsavel", "tecnico_nome",
            "total_participantes", "atrasada", "google_calendar_sync_status",
            "ativo", "criado_em",
        ]
        read_only_fields = fields

    def get_total_participantes(self, obj):
        return obj.membros_participantes.count()

    def get_atrasada(self, obj):
        if obj.status in STATUS_TERMINAIS:
            return False
        return obj.data_fim < timezone.now()


class ActivityDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para criação, atualização e detalhe de atividade."""

    # ── Campos read-only calculados ──────────────────────────────────────────
    tipo_atividade_display = serializers.CharField(
        source="get_tipo_atividade_display", read_only=True
    )
    forma_atuacao_display = serializers.CharField(
        source="get_forma_atuacao_display", read_only=True
    )
    ambito_display = serializers.CharField(
        source="get_ambito_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    atrasada = serializers.SerializerMethodField()
    total_participantes = serializers.SerializerMethodField()
    transicoes_permitidas = serializers.SerializerMethodField()
    territorio_id = serializers.SerializerMethodField()

    # ── FKs writeables ───────────────────────────────────────────────────────
    acao = serializers.PrimaryKeyRelatedField(
        queryset=WorkPlanAcao.objects.all()
    )
    municipio = serializers.PrimaryKeyRelatedField(
        queryset=Municipality.objects.all()
    )
    comunidade = serializers.PrimaryKeyRelatedField(
        queryset=Comunidade.objects.filter(ativa=True),
        required=False, allow_null=True,
    )

    # ── M2M writeables (aceita lista de PKs) ─────────────────────────────────
    equipe_adicional = serializers.PrimaryKeyRelatedField(
        queryset=Activity.equipe_adicional.field.related_model.objects.all(),
        many=True, required=False,
    )
    upfs_participantes = serializers.PrimaryKeyRelatedField(
        queryset=UPF.objects.filter(ativa=True),
        many=True, required=False,
    )
    membros_participantes = serializers.PrimaryKeyRelatedField(
        queryset=MembroFamilia.objects.all(),
        many=True, required=False,
    )

    def _get_upfs_visiveis(self):
        user = self.context["request"].user
        from apps.sgp.views import upfs_acessiveis_ao_usuario
        return upfs_acessiveis_ao_usuario(user)

    def validate_upfs_participantes(self, value):
        upfs_visiveis_pks = set(self._get_upfs_visiveis().values_list("pk", flat=True))
        invalidas = [upf.pk for upf in value if upf.pk not in upfs_visiveis_pks]
        if invalidas:
            raise serializers.ValidationError(
                f"UPFs {invalidas} não são acessíveis ao seu perfil."
            )
        return value

    def validate_membros_participantes(self, value):
        upfs_visiveis_pks = set(self._get_upfs_visiveis().values_list("pk", flat=True))
        invalidos = [
            m.pk for m in value
            if not m.upf_id or m.upf_id not in upfs_visiveis_pks
        ]
        if invalidos:
            raise serializers.ValidationError(
                f"Membros {invalidos} não pertencem a UPFs acessíveis ao seu perfil."
            )
        return value

    class Meta:
        model = Activity
        fields = [
            "id",
            # Identificação
            "titulo", "tipo_atividade", "tipo_atividade_display",
            # Vínculos PT
            "acao",
            # Atuação
            "forma_atuacao", "forma_atuacao_display",
            # Equipe
            "tecnico_responsavel", "equipe_adicional",
            # Localização
            "municipio", "territorio_id",
            "comunidade", "ambito", "ambito_display",
            "latitude", "longitude",
            # Datas
            "data_inicio", "data_fim",
            # Participantes
            "upfs_participantes", "membros_participantes",
            "total_participantes",
            # Parceiros
            "parceiros",
            # Narrativa
            "descricao_narrativa", "resultados_alcancados",
            # Status
            "status", "status_display",
            "justificativa",
            "atrasada", "transicoes_permitidas",
            # Soft-delete
            "ativo",
            # Auditoria
            "criado_por", "criado_em", "atualizado_em",
            # Sync SCA
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
            # Google Calendar
            "google_calendar_event_id", "google_calendar_sync_status",
        ]
        read_only_fields = [
            "id", "criado_por", "criado_em", "atualizado_em",
            "tipo_atividade_display", "forma_atuacao_display",
            "ambito_display", "status_display",
            "atrasada", "total_participantes", "transicoes_permitidas",
            "territorio_id", "google_calendar_event_id",
            "google_calendar_sync_status",
            "device_id", "uuid_local", "ultima_origem", "ultimo_sync_em",
        ]

    # ── SerializerMethodFields ───────────────────────────────────────────────

    def get_atrasada(self, obj):
        if obj.status in STATUS_TERMINAIS:
            return False
        return obj.data_fim < timezone.now()

    def get_total_participantes(self, obj):
        return obj.membros_participantes.count()

    def get_transicoes_permitidas(self, obj):
        return sorted(obj.get_transicoes_permitidas())

    def get_territorio_id(self, obj):
        return obj.territorio_id

    # ── Validação de transição de status ─────────────────────────────────────

    def _validate_status_transition(self, novo_status: str) -> None:
        """Valida se a transição do status atual para o novo é permitida."""
        if self.instance is None:
            # Criação: status inicial deve ser 'planejado' ou outro estado inicial válido
            status_iniciais = {"planejado", "agendado"}
            if novo_status not in status_iniciais:
                raise serializers.ValidationError({
                    "status": (
                        f"Ao criar uma atividade o status inicial deve ser "
                        f"'planejado' ou 'agendado'. Recebido: '{novo_status}'."
                    ),
                    "code": "VALIDATION_ERROR",
                })
            return

        status_atual = self.instance.status
        if novo_status == status_atual:
            return  # sem mudança — ok

        permitidos = STATUS_TRANSITIONS.get(status_atual, set())
        if novo_status not in permitidos:
            raise serializers.ValidationError({
                "status": (
                    f"Transição inválida: '{status_atual}' → '{novo_status}'. "
                    f"Transições permitidas a partir de '{status_atual}': "
                    f"{sorted(permitidos) if permitidos else ['nenhuma (estado terminal)']}"
                ),
                "code": "VALIDATION_ERROR",
            })

    # ── Validações de campo ───────────────────────────────────────────────────

    def validate_data_fim(self, value):
        data_inicio = self.initial_data.get("data_inicio")
        if data_inicio and value:
            from rest_framework.fields import DateTimeField as DRFDateTimeField
            try:
                di = DRFDateTimeField().to_internal_value(data_inicio)
                if value < di:
                    raise serializers.ValidationError(
                        "data_fim não pode ser anterior a data_inicio."
                    )
            except Exception:
                pass  # deixa a validação de data_inicio cuidar
        return value

    # ── Validação cruzada (validate) ──────────────────────────────────────────

    def validate(self, attrs):
        novo_status = attrs.get("status")

        # Validação de transição de status
        if novo_status is not None:
            self._validate_status_transition(novo_status)
        else:
            novo_status = self.instance.status if self.instance else "planejado"

        # Justificativa obrigatória para estados de encerramento sem conclusão
        status_exige_justificativa = {"nao_realizada", "cancelada"}
        justificativa = attrs.get(
            "justificativa",
            self.instance.justificativa if self.instance else "",
        )
        if novo_status in status_exige_justificativa and not justificativa:
            raise serializers.ValidationError({
                "justificativa": (
                    f"Justificativa é obrigatória quando o status é "
                    f"'{novo_status}'."
                ),
                "code": "VALIDATION_ERROR",
            })

        # Regra de negócio: concluido exige evidência vinculada
        if novo_status == "concluido":
            instance = self.instance
            if instance is not None and not instance.has_evidencias():
                raise serializers.ValidationError({
                    "status": (
                        "Não é possível concluir uma atividade sem ao menos "
                        "uma foto ou documento vinculado. "
                        "Adicione evidências antes de marcar como Concluído."
                    ),
                    "code": "VALIDATION_ERROR",
                })
            elif instance is None:
                raise serializers.ValidationError({
                    "status": (
                        "Não é possível criar uma atividade já com status 'concluido'. "
                        "Inicie como 'planejado' e avance o status progressivamente."
                    ),
                    "code": "VALIDATION_ERROR",
                })

        # Validação cruzada: membros devem pertencer às UPFs selecionadas
        upfs_ids = set()
        if "upfs_participantes" in attrs:
            upfs_ids = {upf.pk for upf in attrs["upfs_participantes"]}
        elif self.instance:
            upfs_ids = set(self.instance.upfs_participantes.values_list("pk", flat=True))

        membros = attrs.get("membros_participantes")
        if membros is not None and upfs_ids:
            invalidos = [m.pk for m in membros if m.upf_id not in upfs_ids]
            if invalidos:
                raise serializers.ValidationError({
                    "membros_participantes": (
                        f"Membros {invalidos} não pertencem às UPFs participantes selecionadas."
                    ),
                })

        return attrs

    # ── Create / Update ───────────────────────────────────────────────────────

    def create(self, validated_data):
        equipe = validated_data.pop("equipe_adicional", [])
        upfs = validated_data.pop("upfs_participantes", [])
        membros = validated_data.pop("membros_participantes", [])

        activity = Activity.objects.create(**validated_data)

        if equipe:
            activity.equipe_adicional.set(equipe)
        if upfs:
            activity.upfs_participantes.set(upfs)
        if membros:
            activity.membros_participantes.set(membros)

        return activity

    def update(self, instance, validated_data):
        equipe = validated_data.pop("equipe_adicional", None)
        upfs = validated_data.pop("upfs_participantes", None)
        membros = validated_data.pop("membros_participantes", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if equipe is not None:
            instance.equipe_adicional.set(equipe)
        if upfs is not None:
            instance.upfs_participantes.set(upfs)
        if membros is not None:
            instance.membros_participantes.set(membros)

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Enriquecer FK com nome para leitura
        data["municipio"] = NestedSerializer(instance.municipio).data
        if instance.comunidade_id:
            data["comunidade"] = NestedSerializer(instance.comunidade).data
        if instance.acao_id:
            data["acao"] = {
                "id": instance.acao.pk,
                "numero": instance.acao.numero,
                "descricao": instance.acao.descricao,
            }
        data["tecnico_responsavel"] = {
            "id": instance.tecnico_responsavel.pk,
            "nome": instance.tecnico_responsavel.nome,
            "email": instance.tecnico_responsavel.email,
        }
        return data


# ---------------------------------------------------------------------------
# Calendar serializer — payload reduzido para grade de calendário
# ---------------------------------------------------------------------------

# Paleta semântica: status → cor HEX do design system PDHC
STATUS_COR_MAP: dict[str, str] = {
    "planejado":              "#6B7280",   # gray-500  — rascunho neutro
    "agendado":               "#3B82F6",   # blue-500  — confirmado
    "em_andamento":           "#F59E0B",   # amber-500 — em curso
    "concluido":              "#10B981",   # emerald-500 — sucesso
    "concluido_sem_evidencia":"#14B8A6",   # teal-500  — alerta leve
    "adiada":                 "#8B5CF6",   # violet-500 — reagendamento
    "nao_realizada":          "#EF4444",   # red-500   — falha
    "cancelada":              "#9CA3AF",   # gray-400  — encerrado
}


class ActivityCalendarioSerializer(serializers.ModelSerializer):
    """
    Payload mínimo para alimentar a grade de calendário (Dia/Semana/Mês).
    Todos os campos derivados são resolvidos a partir de select_related —
    zero queries adicionais por item.
    """
    tipo_atividade_display = serializers.CharField(
        source="get_tipo_atividade_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    atrasada = serializers.SerializerMethodField()
    cor = serializers.SerializerMethodField()
    tecnico_responsavel = serializers.SerializerMethodField()
    municipio = serializers.SerializerMethodField()
    comunidade = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "titulo",
            "tipo_atividade",
            "tipo_atividade_display",
            "status",
            "status_display",
            "google_calendar_sync_status",
            "atrasada",
            "cor",
            "data_inicio",
            "data_fim",
            "tecnico_responsavel",
            "municipio",
            "comunidade",
        ]
        read_only_fields = fields

    def get_atrasada(self, obj) -> bool:
        if obj.status in STATUS_TERMINAIS:
            return False
        from django.utils import timezone
        return obj.data_fim < timezone.now()

    def get_cor(self, obj) -> str:
        return STATUS_COR_MAP.get(obj.status, "#6B7280")

    def get_tecnico_responsavel(self, obj) -> dict:
        u = obj.tecnico_responsavel
        return {"id": u.pk, "nome": u.nome}

    def get_municipio(self, obj) -> dict:
        m = obj.municipio
        return {"id": m.pk, "nome": m.nome}

    def get_comunidade(self, obj) -> dict | None:
        if obj.comunidade_id:
            return {"id": obj.comunidade.pk, "nome": obj.comunidade.nome}
        return None
