import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.sgp.constants import ODS_CHOICES, STATUS_WORKPLAN
from apps.sgp.models import Indicator, WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta
from apps.sgp.models.indicator import DESAGREGACAO_CHOICES, FORMA_MANUAL
from apps.sgp.services.visao_indicador import GRANULARIDADE_PADRAO, GRANULARIDADES
from apps.sgp.services.workplan_access import (
    filter_workplan_actions_for_user,
    filter_workplan_submetas_for_user,
)


def _validar_ods(value):
    if not isinstance(value, list):
        raise serializers.ValidationError("ods_ids deve ser uma lista.")
    valid_ids = {c[0] for c in ODS_CHOICES}
    for item in value:
        if not isinstance(item, int) or item not in valid_ids:
            raise serializers.ValidationError(
                f"ODS inválido: {item}. Valores permitidos: 1–17."
            )
    return value


def _clean_do_model(instance, attrs):
    """Roda `clean()` do model sobre o estado resultante do pedido: as regras de
    consistência do Plano de Trabalho moram no model e valem igual no admin e
    na API.

    Trabalha numa cópia: a instância original ainda é lida depois da validação
    (auditoria de "antes", detecção de mudança de número) e não pode chegar lá
    com os valores novos."""
    candidato = copy.copy(instance)
    for campo, valor in attrs.items():
        setattr(candidato, campo, valor)
    try:
        candidato.clean()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict)


def _ja_existe(queryset, instance) -> bool:
    """Unicidade checada no serializer, com mensagem própria, fora o próprio registro."""
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)
    return queryset.exists()


# ---------------------------------------------------------------------------
# Indicador
# ---------------------------------------------------------------------------

class IndicatorSerializer(serializers.ModelSerializer):
    confirmar_recalculo = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text=(
            "Obrigatório ao trocar a forma de apuração de um Indicador com Ações: "
            "confirma o recálculo das quantidades já apuradas."
        ),
    )
    total_acoes = serializers.SerializerMethodField()

    class Meta:
        model = Indicator
        fields = [
            "id", "codigo", "nome", "unidade_medida", "forma_apuracao", "categoria",
            "ods_ids", "desagregacoes", "ativo", "total_acoes", "confirmar_recalculo",
            "criado_por", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "criado_por", "criado_em", "atualizado_em"]
        # A unicidade é checada em `validate_codigo`, depois de normalizar para
        # maiúsculas; o validador padrão compararia o valor ainda cru.
        extra_kwargs = {"codigo": {"validators": []}}

    def get_total_acoes(self, obj) -> int:
        anotado = getattr(obj, "_total_acoes", None)
        return anotado if anotado is not None else obj.acoes.count()

    def validate_codigo(self, value):
        codigo = Indicator.normalizar_codigo(value)
        if _ja_existe(Indicator.objects.filter(codigo=codigo), self.instance):
            raise serializers.ValidationError("Já existe um Indicador com este código.")
        return codigo

    def validate_ods_ids(self, value):
        return _validar_ods(value)

    def validate_desagregacoes(self, value):
        validas = {chave for chave, _ in DESAGREGACAO_CHOICES}
        if not isinstance(value, list) or any(item not in validas for item in value):
            raise serializers.ValidationError(
                f"Use uma lista com valores entre: {', '.join(sorted(validas))}."
            )
        return list(dict.fromkeys(value))


class IndicatorResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Indicator
        fields = ["id", "codigo", "nome", "unidade_medida", "forma_apuracao"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Ação
# ---------------------------------------------------------------------------

class WorkPlanAcaoSerializer(serializers.ModelSerializer):
    submeta_numero = serializers.CharField(source="submeta.numero", read_only=True)
    indicador_detalhe = IndicatorResumoSerializer(source="indicador", read_only=True)
    # Débito técnico: alias de transição do antigo `tipo_unidade`, que o
    # Indicador substituiu. Só existe até o front ler `indicador_detalhe`
    # (ver "Débito técnico" em backend/docs/plano-trabalho.md).
    tipo_unidade_display = serializers.CharField(source="indicador.nome", read_only=True)
    valor_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    valor_executado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    percentual_realizado = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )
    custo_unitario_realizado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, allow_null=True
    )
    # Decimal na saída, como antes das formas de apuração; na entrada (só na
    # forma manual) precisa ser inteiro, porque o campo guarda unidades.
    quantidade_realizada = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )
    status_execucao = serializers.CharField(read_only=True)

    class Meta:
        model = WorkPlanAcao
        fields = [
            "id",
            "meta",
            "submeta",
            "submeta_numero",
            "indicador",
            "indicador_detalhe",
            "tipo_unidade_display",
            "numero",
            "descricao",
            "quantidade_planejada",
            "valor_unitario",
            "valor_total",
            "quantidade_realizada",
            "percentual_realizado",
            "valor_executado",
            "custo_unitario_realizado",
            "data_inicio",
            "data_fim",
            "status_execucao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "meta",
            "valor_total",
            "status_execucao",
            "criado_em",
            "atualizado_em",
        ]
        # A unicidade (submeta, numero) é checada em `validate`, com mensagem própria.
        validators = []

    def validate(self, attrs):
        instance = self.instance
        indicador = attrs.get("indicador", instance.indicador if instance else None)
        if "quantidade_realizada" in attrs and indicador.forma_apuracao != FORMA_MANUAL:
            raise serializers.ValidationError({
                "quantidade_realizada": (
                    "A quantidade realizada é apurada automaticamente para este "
                    "Indicador; só é lançada à mão na forma de apuração manual."
                )
            })

        submeta = attrs.get("submeta", instance.submeta if instance else None)
        # `meta` é só leitura (vem da Submeta), mas quem a envia não pode
        # mandar uma Meta diferente da Submeta escolhida.
        meta_enviada = self.initial_data.get("meta")
        if meta_enviada not in (None, "") and submeta is not None and str(meta_enviada) != str(submeta.meta_id):
            raise serializers.ValidationError(
                {"meta": "A Submeta informada pertence a outra Meta."}
            )
        numero = attrs.get("numero", instance.numero if instance else None)
        if _ja_existe(WorkPlanAcao.objects.filter(submeta=submeta, numero=numero), instance):
            raise serializers.ValidationError(
                {"numero": "Já existe uma Ação com este número nesta Submeta."}
            )

        _clean_do_model(instance or WorkPlanAcao(), attrs)
        return attrs

    def validate_quantidade_realizada(self, value):
        if value != value.to_integral_value():
            raise serializers.ValidationError("Informe um número inteiro de unidades.")
        return int(value)


class WorkPlanAcaoListSerializer(WorkPlanAcaoSerializer):
    class Meta(WorkPlanAcaoSerializer.Meta):
        fields = [
            campo for campo in WorkPlanAcaoSerializer.Meta.fields if campo != "atualizado_em"
        ]


# ---------------------------------------------------------------------------
# Submeta
# ---------------------------------------------------------------------------

class WorkPlanSubmetaSerializer(serializers.ModelSerializer):
    quantidade_planejada = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    quantidade_realizada = serializers.IntegerField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    valor_executado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    status_execucao = serializers.CharField(read_only=True)
    criado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = WorkPlanSubmeta
        fields = [
            "id", "meta", "numero", "titulo", "descricao", "data_inicio", "data_fim",
            "responsavel", "quantidade_planejada", "quantidade_realizada", "valor_total",
            "valor_executado", "status_execucao", "criado_por", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "criado_por", "criado_em", "atualizado_em"]
        validators = []

    def validate(self, attrs):
        instance = self.instance
        meta = attrs.get("meta", instance.meta if instance else None)
        numero = attrs.get("numero", instance.numero if instance else None)
        if _ja_existe(WorkPlanSubmeta.objects.filter(meta=meta, numero=numero), instance):
            raise serializers.ValidationError(
                {"numero": "Já existe uma Submeta com este número nesta Meta."}
            )

        _clean_do_model(instance or WorkPlanSubmeta(), attrs)
        return attrs


class WorkPlanSubmetaDetailSerializer(WorkPlanSubmetaSerializer):
    acoes = serializers.SerializerMethodField()

    class Meta(WorkPlanSubmetaSerializer.Meta):
        fields = WorkPlanSubmetaSerializer.Meta.fields + ["acoes"]

    def get_acoes(self, obj):
        return WorkPlanAcaoSerializer(
            _acoes_visiveis(obj.acoes.all(), self.context), many=True, context=self.context
        ).data


def _acoes_visiveis(queryset, context):
    request = context.get("request")
    queryset = queryset.select_related("submeta", "indicador")
    if request is not None and request.user.is_authenticated:
        queryset = filter_workplan_actions_for_user(queryset, request.user)
    return queryset


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

class WorkPlanMetaListSerializer(serializers.ModelSerializer):
    valor_total_planejado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    status_calculado = serializers.CharField(read_only=True)
    criado_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = WorkPlanMeta
        fields = [
            "id",
            "numero",
            "titulo",
            "data_inicio",
            "data_fim",
            "valor_total_planejado",
            "status_calculado",
            "criado_por",
            "criado_em",
        ]
        read_only_fields = fields


class WorkPlanMetaDetailSerializer(serializers.ModelSerializer):
    valor_total_planejado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    quantidade_planejada = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    valor_executado = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    status_calculado = serializers.CharField(read_only=True)
    criado_por = serializers.StringRelatedField(read_only=True)
    submetas = serializers.SerializerMethodField()
    acoes = serializers.SerializerMethodField()

    class Meta:
        model = WorkPlanMeta
        fields = [
            "id",
            "numero",
            "titulo",
            "descricao",
            "ods_ids",
            "data_inicio",
            "data_fim",
            "quantidade_planejada",
            "valor_total_planejado",
            "valor_executado",
            "status_calculado",
            "criado_por",
            "criado_em",
            "atualizado_em",
            "submetas",
            "acoes",
        ]
        read_only_fields = [
            "id",
            "valor_total_planejado",
            "status_calculado",
            "criado_por",
            "criado_em",
            "atualizado_em",
            "submetas",
            "acoes",
        ]

    def validate_numero(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError(
                "Número da meta deve estar entre 1 e 7."
            )
        if _ja_existe(WorkPlanMeta.objects.filter(numero=value), self.instance):
            raise serializers.ValidationError(
                "Já existe uma meta com este número."
            )
        return value

    def validate_ods_ids(self, value):
        return _validar_ods(value)

    def validate(self, attrs):
        _clean_do_model(self.instance or WorkPlanMeta(), attrs)
        return attrs

    def _acoes_serializadas(self, obj) -> list[dict]:
        """Ações visíveis da Meta, serializadas uma vez só: alimentam `acoes`
        (lista plana, como antes das Submetas) e as `acoes` de cada Submeta."""
        cache = self.__dict__.setdefault("_acoes_por_meta", {})
        if obj.pk not in cache:
            cache[obj.pk] = WorkPlanAcaoSerializer(
                _acoes_visiveis(obj.acoes.all(), self.context),
                many=True,
                context=self.context,
            ).data
        return cache[obj.pk]

    def get_submetas(self, obj):
        submetas = obj.submetas.all()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            submetas = filter_workplan_submetas_for_user(submetas, request.user)
        acoes = self._acoes_serializadas(obj)
        return [
            {
                **WorkPlanSubmetaSerializer(submeta, context=self.context).data,
                "acoes": [acao for acao in acoes if acao["submeta"] == submeta.pk],
            }
            for submeta in submetas
        ]

    def get_acoes(self, obj):
        return self._acoes_serializadas(obj)


# ---------------------------------------------------------------------------
# Painel e exportação
# ---------------------------------------------------------------------------

class WorkPlanDashboardQuerySerializer(serializers.Serializer):
    """Valida os filtros aceitos pelo painel do Plano de Trabalho."""

    meta_id = serializers.IntegerField(min_value=1, required=False)
    territorio_id = serializers.IntegerField(min_value=1, required=False)
    status_execucao = serializers.ChoiceField(
        choices=STATUS_WORKPLAN, required=False
    )


class WorkPlanExportQuerySerializer(serializers.Serializer):
    formato = serializers.ChoiceField(choices=["csv", "xlsx"])
    meta_id = serializers.IntegerField(min_value=1, required=False)
    territorio_id = serializers.IntegerField(min_value=1, required=False)
    periodo_inicio = serializers.DateField(required=False)
    periodo_fim = serializers.DateField(required=False)

    def validate(self, attrs):
        if (
            attrs.get("periodo_inicio")
            and attrs.get("periodo_fim")
            and attrs["periodo_inicio"] > attrs["periodo_fim"]
        ):
            raise serializers.ValidationError(
                "periodo_inicio não pode ser posterior a periodo_fim."
            )
        return attrs


class WorkPlanVisaoIndicadorQuerySerializer(serializers.Serializer):
    territorio_id = serializers.IntegerField(min_value=1, required=False)
    meta_id = serializers.IntegerField(min_value=1, required=False)
    indicador_id = serializers.IntegerField(min_value=1, required=False)
    periodo_inicio = serializers.DateField(required=False)
    periodo_fim = serializers.DateField(required=False)
    granularidade = serializers.ChoiceField(
        choices=list(GRANULARIDADES), default=GRANULARIDADE_PADRAO,
        help_text="Fatia da quebra por período (`por_periodo`).",
    )

    def validate(self, attrs):
        if (
            attrs.get("periodo_inicio")
            and attrs.get("periodo_fim")
            and attrs["periodo_inicio"] > attrs["periodo_fim"]
        ):
            raise serializers.ValidationError(
                "periodo_inicio não pode ser posterior a periodo_fim."
            )
        return attrs


class _NoVisaoIndicadorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.CharField()
    titulo = serializers.CharField()
    quantidade_planejada = serializers.DecimalField(max_digits=14, decimal_places=2)
    quantidade_realizada = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    percentual_realizado = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)


class _TerritorioVisaoIndicadorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    quantidade_realizada = serializers.IntegerField()


class _PeriodoVisaoIndicadorSerializer(serializers.Serializer):
    inicio = serializers.DateField()
    fim = serializers.DateField()
    quantidade_realizada = serializers.IntegerField()


class VisaoIndicadorSerializer(serializers.Serializer):
    """Planejado e realizado de um Indicador somando todas as Ações que o usam.
    `por_territorio` e `por_periodo` só trazem realizado (o planejado não é
    territorial nem datado) e deixam de fora as Ações de apuração manual, que
    não têm território nem data; pelo mesmo motivo, o realizado de um
    Indicador manual vem nulo quando se pede território ou período."""

    indicador = IndicatorResumoSerializer()
    quantidade_planejada = serializers.DecimalField(max_digits=14, decimal_places=2)
    quantidade_realizada = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    percentual_realizado = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    por_meta = _NoVisaoIndicadorSerializer(many=True)
    por_submeta = _NoVisaoIndicadorSerializer(many=True)
    por_territorio = _TerritorioVisaoIndicadorSerializer(many=True)
    por_periodo = _PeriodoVisaoIndicadorSerializer(many=True)


class VisaoPorIndicadorRespostaSerializer(serializers.Serializer):
    granularidade = serializers.ChoiceField(choices=list(GRANULARIDADES))
    indicadores = VisaoIndicadorSerializer(many=True)


class WorkPlanDashboardMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkPlanMeta
        fields = ["id", "numero", "titulo"]


class WorkPlanDashboardSubmetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkPlanSubmeta
        fields = ["id", "numero", "titulo"]


class WorkPlanDashboardNodeSerializer(serializers.Serializer):
    """Consolidado de um nó da árvore do painel (Submeta ou Meta)."""

    quantidade_planejada = serializers.DecimalField(max_digits=14, decimal_places=2)
    quantidade_realizada = serializers.DecimalField(max_digits=14, decimal_places=2)
    percentual_realizado = serializers.DecimalField(max_digits=7, decimal_places=2)
    progresso_esperado = serializers.DecimalField(max_digits=7, decimal_places=2)
    semaforo = serializers.CharField()
    status_execucao = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=14, decimal_places=2)
    percentual_financeiro = serializers.DecimalField(max_digits=7, decimal_places=2)
    semaforo_financeiro = serializers.CharField()


class WorkPlanDashboardAcaoSerializer(serializers.Serializer):
    """Representação de uma Ação e de seus indicadores calculados."""

    id = serializers.IntegerField(read_only=True)
    meta = WorkPlanDashboardMetaSerializer(read_only=True)
    submeta = serializers.IntegerField(source="submeta_id", read_only=True)
    submeta_numero = serializers.CharField(source="submeta.numero", read_only=True)
    submeta_titulo = serializers.CharField(source="submeta.titulo", read_only=True)
    indicador = IndicatorResumoSerializer(read_only=True)
    numero = serializers.CharField(read_only=True)
    descricao = serializers.CharField(read_only=True)
    quantidade_planejada = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    quantidade_realizada = serializers.DecimalField(
        source="dashboard_quantidade_realizada",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    percentual_realizado = serializers.DecimalField(
        source="dashboard_percentual_realizado",
        max_digits=7,
        decimal_places=2,
        read_only=True,
    )
    progresso_esperado = serializers.DecimalField(
        source="dashboard_progresso_esperado",
        max_digits=7,
        decimal_places=2,
        read_only=True,
    )
    semaforo = serializers.CharField(source="dashboard_semaforo", read_only=True)
    status_execucao = serializers.CharField(
        source="dashboard_status_execucao", read_only=True
    )
    valor_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    valor_executado = serializers.DecimalField(
        source="dashboard_valor_executado",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    percentual_financeiro = serializers.DecimalField(
        source="dashboard_percentual_financeiro",
        max_digits=7,
        decimal_places=2,
        read_only=True,
    )
    semaforo_financeiro = serializers.CharField(
        source="dashboard_semaforo_financeiro", read_only=True
    )
    data_inicio = serializers.DateField(read_only=True)
    data_fim = serializers.DateField(read_only=True)
