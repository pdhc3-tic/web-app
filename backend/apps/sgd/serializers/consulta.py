from rest_framework import serializers

_DEC = dict(max_digits=14, decimal_places=2)


class PainelRubricaSerializer(serializers.Serializer):
    rubrica_id = serializers.IntegerField()
    rubrica_slug = serializers.CharField()
    rubrica_nome = serializers.CharField()
    solicitado = serializers.DecimalField(**_DEC)
    autorizado = serializers.DecimalField(**_DEC)
    executado = serializers.DecimalField(**_DEC)
    disponivel = serializers.DecimalField(**_DEC)


class CustoPorAtividadeSerializer(serializers.Serializer):
    atividade_id = serializers.IntegerField()
    atividade_titulo = serializers.CharField()
    demandas = serializers.IntegerField()
    estimado = serializers.DecimalField(**_DEC)
    autorizado = serializers.DecimalField(**_DEC)
    pago = serializers.DecimalField(**_DEC)


class CustoPorEntregaSerializer(serializers.Serializer):
    acao_id = serializers.IntegerField()
    acao_numero = serializers.CharField()
    acao_descricao = serializers.CharField()
    demandas = serializers.IntegerField()
    estimado = serializers.DecimalField(**_DEC)
    autorizado = serializers.DecimalField(**_DEC)
    pago = serializers.DecimalField(**_DEC)
    atividades = CustoPorAtividadeSerializer(many=True)
