from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.sgd.serializers.tipo_solicitacao import SlugDeTipoField


class SaldoConsultaQuerySerializer(serializers.Serializer):
    activity_id = serializers.IntegerField(
        required=False, help_text="Ignorado: o saldo depende só do solicitante e da rubrica.",
    )
    rubrica = serializers.CharField(required=False, help_text="slug de BudgetRubrica")
    tipo = SlugDeTipoField(
        required=False, help_text="tipo de solicitação; a rubrica sai do catálogo de tipos",
    )
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)

    def validate(self, attrs):
        if ("rubrica" in attrs) == ("tipo" in attrs):
            raise serializers.ValidationError("Informe exatamente um entre 'rubrica' e 'tipo'.")
        return attrs


class TravaSerializer(serializers.Serializer):
    disponivel = serializers.BooleanField()
    saldo = serializers.DecimalField(max_digits=14, decimal_places=2)
    motivo_bloqueio = serializers.CharField(allow_null=True)
    acao_sugerida = serializers.CharField(allow_null=True)
    semaforo_atual = serializers.CharField(allow_null=True)
    semaforo_apos = serializers.CharField(allow_null=True)


# Nome próprio no schema: `apps.sgp.budget.serializers` tem um homônimo.
@extend_schema_serializer(component_name="SaldoConsultaDemanda")
class SaldoConsultaSerializer(serializers.Serializer):
    rubrica_slug = serializers.CharField()
    rubrica_nome = serializers.CharField()
    individual = TravaSerializer()
    territorial = TravaSerializer()
    disponivel = serializers.BooleanField()
    trava_bloqueada = serializers.CharField(allow_null=True)
