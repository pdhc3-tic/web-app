from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.sgd.models.diarias import EnquadramentoFaixaDiaria, FaixaDestinoDiaria, OrigemValorDiaria, TabelaDiaria


class SimularDiariasQuerySerializer(serializers.Serializer):
    municipio_destino_id = serializers.IntegerField()
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    hospedagem_custeada = serializers.BooleanField(required=False, default=False)


class FaixaDestinoSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField()


class SimulacaoDiariasSerializer(serializers.Serializer):
    faixa_destino = FaixaDestinoSerializer()
    tabela_diaria_id = serializers.IntegerField()
    valor_por_diaria = serializers.DecimalField(max_digits=14, decimal_places=2)
    numero_diarias = serializers.DecimalField(max_digits=6, decimal_places=1)
    adicional_embarque = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_total = serializers.DecimalField(max_digits=14, decimal_places=2)


# --- Configuração ---------------------------------------------------------------------


class EnquadramentoSerializer(serializers.ModelSerializer):
    codigo_ibge = serializers.RegexField(r"^\d{7}$", error_messages={"invalid": "Informe os 7 dígitos do código IBGE."})

    class Meta:
        model = EnquadramentoFaixaDiaria
        fields = ["codigo_ibge", "nome_referencia"]


class FaixaDestinoDiariaSerializer(serializers.ModelSerializer):
    """`enquadramentos`, quando enviado, substitui a lista de municípios da faixa."""

    enquadramentos = EnquadramentoSerializer(many=True, required=False)

    class Meta:
        model = FaixaDestinoDiaria
        fields = ["id", "nome", "ordem", "padrao", "ativo", "enquadramentos", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_enquadramentos(self, itens):
        codigos = [item["codigo_ibge"] for item in itens]
        repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
        if repetidos:
            raise serializers.ValidationError(f"Códigos repetidos: {', '.join(repetidos)}.")
        outras = EnquadramentoFaixaDiaria.objects.filter(codigo_ibge__in=codigos).select_related("faixa")
        if self.instance is not None:
            outras = outras.exclude(faixa=self.instance)
        conflitos = [f"{e.codigo_ibge} ({e.faixa.nome})" for e in outras]
        if conflitos:
            raise serializers.ValidationError(
                f"Município já enquadrado em outra faixa: {', '.join(conflitos)}. Remova-o de lá primeiro.",
            )
        return itens

    def _gravar_enquadramentos(self, faixa, itens):
        if itens is None:
            return
        faixa.enquadramentos.all().delete()
        EnquadramentoFaixaDiaria.objects.bulk_create(
            [EnquadramentoFaixaDiaria(faixa=faixa, **item) for item in itens],
        )

    @transaction.atomic
    def create(self, validated_data):
        itens = validated_data.pop("enquadramentos", [])
        faixa = super().create(validated_data)
        self._gravar_enquadramentos(faixa, itens)
        return faixa

    @transaction.atomic
    def update(self, instance, validated_data):
        itens = validated_data.pop("enquadramentos", None)
        faixa = super().update(instance, validated_data)
        self._gravar_enquadramentos(faixa, itens)
        return faixa


class TabelaDiariaSerializer(serializers.ModelSerializer):
    faixa_destino_nome = serializers.CharField(source="faixa_destino.nome", read_only=True)
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    criado_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = TabelaDiaria
        fields = [
            "id", "faixa_destino", "faixa_destino_nome", "categoria_beneficiario", "vigencia_inicio",
            "vigencia_fim", "valor", "origem", "criado_por", "criado_por_nome", "criado_em",
        ]
        read_only_fields = ["id", "criado_por", "criado_em"]

    def get_criado_por_nome(self, obj) -> str | None:
        usuario = obj.criado_por
        if usuario is None:
            return None
        return usuario.nome or usuario.email

    def validate(self, attrs):
        inicio, fim = attrs.get("vigencia_inicio"), attrs.get("vigencia_fim")
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError({"vigencia_fim": "Não pode ser anterior ao início da vigência."})
        return attrs


class NovaVigenciaSerializer(serializers.Serializer):
    """Editar um valor da tabela: cria uma vigência nova a partir de `vigencia_inicio`."""

    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    vigencia_inicio = serializers.DateField()
    origem = serializers.ChoiceField(choices=OrigemValorDiaria.choices)


class ParametrosDiariasSerializer(serializers.Serializer):
    """Regras de contagem e adicional de embarque, guardados como parâmetros do Core."""

    regra_inteira_por_pernoite = serializers.BooleanField(required=False)
    regra_meia_no_retorno = serializers.BooleanField(required=False)
    regra_meia_sem_pernoite = serializers.BooleanField(required=False)
    regra_meia_hospedagem_custeada = serializers.BooleanField(required=False)
    adicional_embarque_ativo = serializers.BooleanField(required=False)
    adicional_embarque_valor = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False,
    )
