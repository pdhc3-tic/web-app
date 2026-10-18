from rest_framework import serializers

_DEC = dict(max_digits=14, decimal_places=2)


class DashboardFilaItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    status = serializers.CharField()
    status_alterado_em = serializers.DateTimeField()
    dias_em_espera = serializers.IntegerField()
    valor_estimado = serializers.DecimalField(**_DEC)
    atividade_id = serializers.IntegerField()
    atividade_titulo = serializers.CharField()
    estado = serializers.CharField()
    territorio = serializers.CharField(allow_null=True)


class DashboardFilaSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    itens = DashboardFilaItemSerializer(many=True)


class DashboardStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    rotulo = serializers.CharField()
    total = serializers.IntegerField()


class DashboardAlertaSaldoSerializer(serializers.Serializer):
    meta_id = serializers.IntegerField()
    meta_numero = serializers.CharField()
    rubrica_id = serializers.IntegerField()
    rubrica_slug = serializers.CharField()
    rubrica_nome = serializers.CharField()
    nivel = serializers.CharField()
    faixa = serializers.ChoiceField(choices=["amarelo", "vermelho"])
    percentual_comprometido = serializers.DecimalField(max_digits=7, decimal_places=2)
    valor_aprovado = serializers.DecimalField(**_DEC)
    valor_comprometido = serializers.DecimalField(**_DEC)
    saldo_disponivel = serializers.DecimalField(**_DEC)


class DashboardParadaItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    status = serializers.CharField()
    status_alterado_em = serializers.DateTimeField()
    dias_uteis_parada = serializers.IntegerField()
    estado = serializers.CharField()


class DashboardParadasSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    itens = DashboardParadaItemSerializer(many=True)


class DashboardSerializer(serializers.Serializer):
    perfis = serializers.ListField(child=serializers.CharField())
    fila_aguardando_acao = DashboardFilaSerializer()
    contagem_por_status = DashboardStatusSerializer(many=True)
    alertas_saldo = DashboardAlertaSaldoSerializer(many=True)
    sem_movimentacao = DashboardParadasSerializer()
