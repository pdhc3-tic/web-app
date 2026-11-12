from decimal import Decimal

from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.serializers.tipo_solicitacao import SlugDeTipoField
from apps.sgd.services import anexos as anexos_service
from apps.sgd.services.approval import alerta_rubrica_fora_do_previsto
from apps.sgd.services.tipos_solicitacao import obter_validador


_ANEXO_DO_CAMPO = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "nome_original": {"type": "string"},
        "download": {"type": "string", "description": "Rota que devolve a URL assinada do arquivo."},
    },
    "required": ["id", "nome_original", "download"],
}


class DemandRequestSerializer(serializers.ModelSerializer):
    tipo = serializers.CharField(source="tipo_id", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    rubrica_slug = serializers.CharField(source="rubrica.slug", read_only=True)
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)
    alerta_rubrica_fora_do_previsto = serializers.SerializerMethodField()
    anexos = serializers.SerializerMethodField()

    class Meta:
        model = DemandRequest
        fields = [
            "id", "demanda", "tipo", "tipo_display", "rubrica", "rubrica_slug", "rubrica_nome",
            "campos_json", "valor_estimado", "valor_autorizado", "valor_pago", "ordem",
            "alerta_rubrica_fora_do_previsto", "anexos", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "demanda", "rubrica", "valor_autorizado", "valor_pago", "criado_em", "atualizado_em"]

    def get_alerta_rubrica_fora_do_previsto(self, obj):
        return alerta_rubrica_fora_do_previsto(obj)

    @extend_schema_field({
        "type": "object",
        "description": (
            "Um item por campo de anexo do schema: o documento (campo de um arquivo, `null` "
            "se vazio) ou a lista deles (campo de vários)."
        ),
        "additionalProperties": {
            "oneOf": [_ANEXO_DO_CAMPO, {"type": "array", "items": _ANEXO_DO_CAMPO}],
            "nullable": True,
        },
    })
    def get_anexos(self, obj) -> dict:
        campos = anexos_service.campos_de_anexo(obj.tipo.schema_campos)
        if not campos:
            return {}
        # `.all()` usa o prefetch da leitura, que já vem só com os ativos; sem ele, filtra aqui.
        documentos = {doc.pk: doc for doc in obj.anexos.all() if doc.ativo}
        anexos = {}
        for campo, multiplo in campos.items():
            # Valor sem a forma do campo (o schema mudou depois da gravação) sai como vazio.
            ids = anexos_service.ids_do_campo(obj.campos_json.get(campo), multiplo=multiplo) or []
            itens = [self._anexo(obj, documentos[doc_id]) for doc_id in ids if doc_id in documentos]
            anexos[campo] = itens if multiplo else (itens[0] if itens else None)
        return anexos

    @staticmethod
    def _anexo(solicitacao, documento) -> dict:
        download = reverse(
            "demanda-documentos-download", kwargs={"pk": solicitacao.demanda_id, "doc_id": documento.pk},
        )
        return {"id": documento.pk, "nome_original": documento.nome_original, "download": download}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        validador = obter_validador(instance.tipo.validador)
        if validador and validador.chave_cpf and instance.beneficiario_cpf:
            data["campos_json"] = {**data["campos_json"], validador.chave_cpf: instance.beneficiario_cpf}
        return data


class DemandRequestCreateSerializer(serializers.Serializer):
    tipo = SlugDeTipoField()
    campos_json = serializers.JSONField()
    valor_estimado = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0.01"),
    )
    ordem = serializers.IntegerField(required=False, default=0)


class DemandRequestUpdateSerializer(serializers.Serializer):
    tipo = SlugDeTipoField(required=False)
    campos_json = serializers.JSONField(required=False)
    valor_estimado = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal("0.01"),
    )
