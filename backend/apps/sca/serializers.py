"""
Serializers do módulo SCA — validação de payloads de sync e refresh.
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Push — payload de cada item do batch
# ---------------------------------------------------------------------------

class TitularSyncSerializer(serializers.Serializer):
    nome_completo = serializers.CharField(required=False, allow_blank=True)
    cpf = serializers.CharField(required=False, allow_blank=True)
    data_nasc = serializers.DateField(required=False, allow_null=True)
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
    data_nasc = serializers.DateField(required=False, allow_null=True)
    genero = serializers.IntegerField(required=False, allow_null=True)
    cor_raca = serializers.IntegerField(required=False, allow_null=True)
    cpf = serializers.CharField(required=False, allow_blank=True)
    rg = serializers.CharField(required=False, allow_blank=True)
    nis = serializers.CharField(required=False, allow_blank=True)
    caf = serializers.CharField(required=False, allow_blank=True)
    parentesco = serializers.CharField(required=False, allow_blank=True)
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
