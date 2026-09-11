from django.utils import timezone
from rest_framework import serializers

from apps.core.models import Municipality, Organization
from apps.sgp.models import Activity, Comunidade, MembroFamilia, UPF, WorkPlanAcao
from apps.sgp.models.activity import STATUS_TERMINAIS, STATUS_TRANSITIONS
from apps.sgp.serializers.activity_documentos import ActivityDocumentSerializer
from apps.sgp.serializers.activity_foto import ActivityPhotoSerializer
from apps.sgp.serializers.common import MunicipioNestedSerializer, NestedSerializer
from apps.sgp.serializers.membro import MembroListSerializer
from apps.sgp.serializers.upf import UPFListSerializer

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
    municipio = MunicipioNestedSerializer(read_only=True)
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
            "municipio",
            "data_inicio", "data_fim",
            "status", "status_display",
            "tecnico_responsavel", "tecnico_nome",
            "total_participantes", "atrasada", "google_calendar_sync_status",
            "ativo", "criado_em",
        ]
        read_only_fields = fields

    def get_total_participantes(self, obj):
        return len(obj.membros_participantes.all())

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
    parceiros_organizacoes = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(ativa=True),
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
            "parceiros_organizacoes", "parceiros_livres",
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
        return len(obj.membros_participantes.all())

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
        parceiros = validated_data.pop("parceiros_organizacoes", [])

        activity = Activity.objects.create(**validated_data)

        if equipe:
            activity.equipe_adicional.set(equipe)
        if upfs:
            activity.upfs_participantes.set(upfs)
        if membros:
            activity.membros_participantes.set(membros)
        if parceiros:
            activity.parceiros_organizacoes.set(parceiros)

        return activity

    def update(self, instance, validated_data):
        equipe = validated_data.pop("equipe_adicional", None)
        upfs = validated_data.pop("upfs_participantes", None)
        membros = validated_data.pop("membros_participantes", None)
        parceiros = validated_data.pop("parceiros_organizacoes", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if equipe is not None:
            instance.equipe_adicional.set(equipe)
        if upfs is not None:
            instance.upfs_participantes.set(upfs)
        if membros is not None:
            instance.membros_participantes.set(membros)
        if parceiros is not None:
            instance.parceiros_organizacoes.set(parceiros)

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Enriquecer FK com nome para leitura
        data["municipio"] = MunicipioNestedSerializer(instance.municipio).data
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
        data["equipe_adicional"] = [
            {"id": u.pk, "nome": u.nome, "email": u.email}
            for u in instance.equipe_adicional.all()
        ]
        data["upfs_participantes"] = UPFListSerializer(
            instance.upfs_participantes.all(), many=True, context=self.context
        ).data
        data["membros_participantes"] = MembroListSerializer(
            instance.membros_participantes.all(), many=True, context=self.context
        ).data
        data["fotos"] = ActivityPhotoSerializer(
            instance.fotos.all(), many=True
        ).data
        data["documentos"] = ActivityDocumentSerializer(
            instance.documentos.all(), many=True
        ).data
        return data
