"""
Serializers do módulo SCA — validação de payloads de sync e refresh,
além dos endpoints administrativos (#156, #157, #158).
"""

from rest_framework import serializers

from apps.sca.models import ConflictLog, SyncDevice, SyncEvent


# ---------------------------------------------------------------------------
# Push — payload de cada item do batch
# ---------------------------------------------------------------------------

class TitularSyncSerializer(serializers.Serializer):
    nome_completo = serializers.CharField(required=False, allow_blank=True)
    cpf = serializers.CharField(required=False, allow_blank=True)
    data_nascimento = serializers.DateField(required=False, allow_null=True)
    genero = serializers.IntegerField(required=False, allow_null=True)
    cor_raca = serializers.IntegerField(required=False, allow_null=True)
    rg = serializers.CharField(required=False, allow_blank=True)
    nis = serializers.CharField(required=False, allow_blank=True)
    caf = serializers.CharField(required=False, allow_blank=True)
    escola = serializers.CharField(required=False, allow_blank=True)
    seguridade_social = serializers.ListField(required=False, default=list)
    saude = serializers.ListField(required=False, default=list)
    escolaridade = serializers.IntegerField(required=False, allow_null=True)


class UPFSyncSerializer(serializers.Serializer):
    projeto = serializers.IntegerField(required=False, allow_null=True)
    comunidade = serializers.IntegerField(required=False, allow_null=True)
    municipio = serializers.IntegerField(required=False, allow_null=True)
    territorio = serializers.IntegerField(required=False, allow_null=True)

    apelido = serializers.CharField(required=False, allow_blank=True)
    whatsapp = serializers.CharField(required=False, allow_blank=True)
    celular = serializers.CharField(required=False, allow_blank=True)
    internet = serializers.BooleanField(required=False)
    dispositivo = serializers.IntegerField(required=False, allow_null=True)
    cep = serializers.CharField(required=False, allow_blank=True)
    logradouro = serializers.CharField(required=False, allow_blank=True)
    numero = serializers.CharField(required=False, allow_blank=True)
    complemento = serializers.CharField(required=False, allow_blank=True)
    bairro = serializers.CharField(required=False, allow_blank=True)

    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)

    pct = serializers.IntegerField(required=False, allow_null=True)
    posse_terra = serializers.IntegerField(required=False, allow_null=True)
    area_terra_ha = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    situacao_moradia = serializers.IntegerField(required=False, allow_null=True)
    tipo_moradia = serializers.IntegerField(required=False, allow_null=True)
    material_construcao = serializers.IntegerField(required=False, allow_null=True)
    num_comodos = serializers.IntegerField(required=False, allow_null=True)
    energia = serializers.IntegerField(required=False, allow_null=True)
    agua = serializers.IntegerField(required=False, allow_null=True)

    numero_dap = serializers.CharField(required=False, allow_blank=True)
    nis = serializers.CharField(required=False, allow_blank=True)
    seguridade_social = serializers.ListField(required=False, default=list)
    foto_url = serializers.URLField(required=False, allow_blank=True)
    ativa = serializers.BooleanField(required=False)

    titular = TitularSyncSerializer(required=False)


class MemberSyncSerializer(serializers.Serializer):
    upf = serializers.IntegerField(required=False, allow_null=True)
    upf_uuid_local = serializers.UUIDField(required=False, allow_null=True)
    nome_completo = serializers.CharField(required=False, allow_blank=True)
    data_nascimento = serializers.DateField(required=False, allow_null=True)
    genero = serializers.IntegerField(required=False, allow_null=True)
    cor_raca = serializers.IntegerField(required=False, allow_null=True)
    cpf = serializers.CharField(required=False, allow_blank=True)
    rg = serializers.CharField(required=False, allow_blank=True)
    nis = serializers.CharField(required=False, allow_blank=True)
    caf = serializers.CharField(required=False, allow_blank=True)
    grau_parentesco = serializers.CharField(required=False, allow_blank=True)
    escola = serializers.CharField(required=False, allow_blank=True)
    seguridade_social = serializers.ListField(required=False, default=list)
    saude = serializers.ListField(required=False, default=list)
    escolaridade = serializers.IntegerField(required=False, allow_null=True)


class ActivitySyncSerializer(serializers.Serializer):
    titulo = serializers.CharField(required=False, allow_blank=True)
    tipo_atividade = serializers.CharField(required=False, allow_blank=True)
    acao = serializers.IntegerField(required=False, allow_null=True)
    forma_atuacao = serializers.CharField(required=False, allow_blank=True)
    municipio = serializers.IntegerField(required=False, allow_null=True)
    comunidade = serializers.IntegerField(required=False, allow_null=True)
    tecnico_responsavel = serializers.IntegerField(required=False, allow_null=True)
    ambito = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    data_inicio = serializers.DateField(required=False, allow_null=True)
    data_fim = serializers.DateField(required=False, allow_null=True)
    parceiros = serializers.CharField(required=False, allow_blank=True)
    descricao_narrativa = serializers.CharField(required=False, allow_blank=True)
    resultados_alcancados = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    justificativa = serializers.CharField(required=False, allow_blank=True)
    upfs_participantes = serializers.ListField(required=False, default=list)
    membros_participantes = serializers.ListField(required=False, default=list)
    ativo = serializers.BooleanField(required=False)


ENTITY_SERIALIZERS = {
    "upf": UPFSyncSerializer,
    "member": MemberSyncSerializer,
    "activity": ActivitySyncSerializer,
}


class PushItemSerializer(serializers.Serializer):
    entidade = serializers.ChoiceField(choices=("upf", "member", "activity", "form_response"))
    uuid_local = serializers.UUIDField()
    operacao = serializers.ChoiceField(choices=("create", "update"))
    payload_json = serializers.DictField()
    base_json = serializers.DictField(required=False, default=dict)
    updated_at = serializers.DateTimeField()
    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


class PushBatchSerializer(serializers.Serializer):
    registros = PushItemSerializer(many=True)
    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# Auth refresh SCA
# ---------------------------------------------------------------------------

class ScaRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()
    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# Endpoints Administrativos SCA (#156, #157, #158)
# ---------------------------------------------------------------------------

class SyncDeviceListSerializer(serializers.ModelSerializer):
    tecnico = serializers.SerializerMethodField()
    territorios = serializers.SerializerMethodField()
    ultimo_sync_servidor = serializers.SerializerMethodField()
    registros_pendentes = serializers.SerializerMethodField()

    class Meta:
        model = SyncDevice
        fields = [
            "id",
            "device_id",
            "nome",
            "modelo",
            "sistema_operacional",
            "app_versao",
            "tecnico",
            "territorios",
            "ultimo_sync_servidor",
            "registros_pendentes",
            "ativo",
        ]

    def get_tecnico(self, obj):
        return {
            "id": obj.user_id,
            "nome": obj.user.nome,
            "email": obj.user.email,
        }

    def get_territorios(self, obj):
        from apps.core.serializers import TerritorySerializer

        mapa = self.context.get("territorios_por_usuario")
        territorios = mapa.get(obj.user_id) if mapa is not None else None
        if territorios is None:
            from apps.core.services.permissions import user_territories

            territorios = list(user_territories(obj.user))
        return TerritorySerializer(territorios, many=True).data

    def get_ultimo_sync_servidor(self, obj):
        dt = getattr(obj, "ultimo_sync_servidor", None) or obj.ultimo_sync_em
        return dt.isoformat() if dt else None

    def get_registros_pendentes(self, obj):
        mapa = self.context.get("registros_pendentes")
        if mapa is not None:
            return mapa.get(obj.pk, 0)
        from apps.sca import services

        return services.count_pending_records(obj.user, obj)


class SyncDeviceDetailSerializer(serializers.ModelSerializer):
    tecnico = serializers.SerializerMethodField()
    territorios = serializers.SerializerMethodField()
    ultimo_sync_servidor = serializers.SerializerMethodField()
    registros_pendentes = serializers.SerializerMethodField()
    registros_por_entidade = serializers.SerializerMethodField()

    class Meta:
        model = SyncDevice
        fields = [
            "id",
            "device_id",
            "nome",
            "modelo",
            "sistema_operacional",
            "app_versao",
            "tecnico",
            "territorios",
            "ultimo_sync_servidor",
            "registros_pendentes",
            "registros_por_entidade",
            "ativo",
            "criado_em",
        ]

    def get_tecnico(self, obj):
        return {
            "id": obj.user_id,
            "nome": obj.user.nome,
            "email": obj.user.email,
        }

    def get_territorios(self, obj):
        from apps.core.serializers import TerritorySerializer
        from apps.core.services.permissions import user_territories

        return TerritorySerializer(list(user_territories(obj.user)), many=True).data

    def get_ultimo_sync_servidor(self, obj):
        dt = getattr(obj, "ultimo_sync_servidor", None) or obj.ultimo_sync_em
        return dt.isoformat() if dt else None

    def get_registros_pendentes(self, obj):
        mapa = self.context.get("registros_por_entidade")
        if mapa is not None:
            return sum(mapa.values())
        from apps.sca import services
        return services.count_pending_records(obj.user, obj)

    def get_registros_por_entidade(self, obj):
        mapa = self.context.get("registros_por_entidade")
        if mapa is not None:
            return mapa
        from apps.sca import services
        return services.count_pending_records_by_entity(obj.user, obj)


class SyncEventListSerializer(serializers.ModelSerializer):
    tecnico = serializers.SerializerMethodField()
    dispositivo = serializers.SerializerMethodField()
    has_erros = serializers.BooleanField(read_only=True)

    class Meta:
        model = SyncEvent
        fields = [
            "id",
            "tipo",
            "since",
            "iniciado_em",
            "finalizado_em",
            "contagem",
            "contagem_enviados",
            "contagem_recebidos",
            "contagem_erros",
            "has_erros",
            "tipo_conexao",
            "tecnico",
            "dispositivo",
        ]

    def get_tecnico(self, obj):
        return {
            "id": obj.user_id,
            "nome": obj.user.nome,
            "email": obj.user.email,
        }

    def get_dispositivo(self, obj):
        if not obj.device:
            return None
        return {
            "id": obj.device_id,
            "device_id": obj.device.device_id,
            "nome": obj.device.nome,
        }


class SyncEventDetailSerializer(SyncEventListSerializer):
    class Meta(SyncEventListSerializer.Meta):
        fields = SyncEventListSerializer.Meta.fields + ["erros_detalhes"]


class ConflictLogListSerializer(serializers.ModelSerializer):
    tecnico = serializers.SerializerMethodField()
    dispositivo = serializers.SerializerMethodField()
    territorio = serializers.SerializerMethodField()
    resolvido_por = serializers.SerializerMethodField()

    class Meta:
        model = ConflictLog
        fields = [
            "id",
            "entidade",
            "uuid_local",
            "campo",
            "valor_local",
            "valor_servidor",
            "estrategia",
            "campo_sensivel",
            "status",
            "valor_final",
            "resolvido_por",
            "resolvido_em",
            "territorio",
            "tecnico",
            "dispositivo",
            "criado_em",
        ]

    def get_tecnico(self, obj):
        return {
            "id": obj.user_id,
            "nome": obj.user.nome,
            "email": obj.user.email,
        }

    def get_dispositivo(self, obj):
        if not obj.device:
            return None
        return {
            "id": obj.device_id,
            "device_id": obj.device.device_id,
            "nome": obj.device.nome,
        }

    def get_territorio(self, obj):
        if not obj.territorio:
            return None
        return {
            "id": obj.territorio_id,
            "nome": obj.territorio.nome,
        }

    def get_resolvido_por(self, obj):
        if not obj.resolvido_por:
            return None
        return {
            "id": obj.resolvido_por_id,
            "nome": obj.resolvido_por.nome,
            "email": obj.resolvido_por.email,
        }


class ConflictLogDetailSerializer(ConflictLogListSerializer):
    registro_atual = serializers.SerializerMethodField()

    class Meta(ConflictLogListSerializer.Meta):
        fields = ConflictLogListSerializer.Meta.fields + ["registro_atual"]

    def get_registro_atual(self, obj):
        from apps.sgp.models import Activity, MembroFamilia, UPF
        from apps.sgp.serializers import (
            ActivityDetailSerializer,
            MembroDetailSerializer,
            UPFDetailSerializer,
        )

        if obj.entidade == "upf":
            upf = UPF.objects.filter(uuid_local=obj.uuid_local).first()
            return UPFDetailSerializer(upf).data if upf else None
        if obj.entidade == "member":
            membro = MembroFamilia.objects.filter(uuid_local=obj.uuid_local).first()
            return MembroDetailSerializer(membro).data if membro else None
        if obj.entidade == "activity":
            act = Activity.objects.filter(uuid_local=obj.uuid_local).first()
            return ActivityDetailSerializer(act).data if act else None
        return None


class ConflictResolveSerializer(serializers.Serializer):
    decisao = serializers.ChoiceField(choices=["local", "servidor", "manual"])
    valor_manual = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["decisao"] == "manual" and "valor_manual" not in attrs:
            raise serializers.ValidationError({"valor_manual": "Obrigatório quando a decisão é manual."})
        return attrs
