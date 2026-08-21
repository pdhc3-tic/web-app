import re

from rest_framework import serializers

from apps.sgp.constants import ODS_CHOICES
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta


class WorkPlanAcaoSerializer(serializers.ModelSerializer):
    tipo_unidade_display = serializers.CharField(
        source="get_tipo_unidade_display", read_only=True
    )
    valor_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    quantidade_realizada = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    status_execucao = serializers.CharField(read_only=True)

    class Meta:
        model = WorkPlanAcao
        fields = [
            "id",
            "meta",
            "numero",
            "descricao",
            "tipo_unidade",
            "tipo_unidade_display",
            "quantidade_planejada",
            "valor_unitario",
            "valor_total",
            "quantidade_realizada",
            "data_inicio",
            "data_fim",
            "status_execucao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "valor_total",
            "quantidade_realizada",
            "status_execucao",
            "criado_em",
            "atualizado_em",
        ]

    def validate_numero(self, value):
        if not re.match(r"^\d+\.\d+$", value):
            raise serializers.ValidationError(
                "Formato inválido. Use X.Y (ex: 1.1, 2.3)."
            )
        meta = self.initial_data.get("meta") if not self.instance else self.instance.meta_id
        if meta:
            qs = WorkPlanAcao.objects.filter(meta_id=meta, numero=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Já existe uma Ação com este número nesta Meta."
                )
        return value


class WorkPlanAcaoListSerializer(serializers.ModelSerializer):
    tipo_unidade_display = serializers.CharField(
        source="get_tipo_unidade_display", read_only=True
    )
    valor_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    quantidade_realizada = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    status_execucao = serializers.CharField(read_only=True)

    class Meta:
        model = WorkPlanAcao
        fields = [
            "id",
            "meta",
            "numero",
            "descricao",
            "tipo_unidade",
            "tipo_unidade_display",
            "quantidade_planejada",
            "valor_unitario",
            "valor_total",
            "quantidade_realizada",
            "data_inicio",
            "data_fim",
            "status_execucao",
            "criado_em",
        ]
        read_only_fields = [
            "id",
            "valor_total",
            "quantidade_realizada",
            "status_execucao",
            "criado_em",
        ]


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
    status_calculado = serializers.CharField(read_only=True)
    criado_por = serializers.StringRelatedField(read_only=True)
    acoes = WorkPlanAcaoSerializer(many=True, read_only=True)

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
            "valor_total_planejado",
            "status_calculado",
            "criado_por",
            "criado_em",
            "atualizado_em",
            "acoes",
        ]
        read_only_fields = [
            "id",
            "valor_total_planejado",
            "status_calculado",
            "criado_por",
            "criado_em",
            "atualizado_em",
            "acoes",
        ]

    def validate_numero(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError(
                "Número da meta deve estar entre 1 e 7."
            )
        qs = WorkPlanMeta.objects.filter(numero=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Já existe uma meta com este número."
            )
        return value

    def validate_ods_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("ods_ids deve ser uma lista.")
        valid_ids = {c[0] for c in ODS_CHOICES}
        for item in value:
            if not isinstance(item, int) or item not in valid_ids:
                raise serializers.ValidationError(
                    f"ODS inválido: {item}. Valores permitidos: 1–17."
                )
        return value


class WorkPlanDashboardQuerySerializer(serializers.Serializer):
    """Valida os filtros aceitos pelo painel do Plano de Trabalho."""

    meta_id = serializers.IntegerField(min_value=1, required=False)
    territorio_id = serializers.IntegerField(min_value=1, required=False)
    status_execucao = serializers.ChoiceField(
        choices=["concluida", "em_atraso", "no_prazo"], required=False
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


class WorkPlanDashboardMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkPlanMeta
        fields = ["id", "numero", "titulo"]


class WorkPlanDashboardAcaoSerializer(serializers.Serializer):
    """Representação de uma Ação e de seus indicadores calculados."""

    id = serializers.IntegerField(read_only=True)
    meta = WorkPlanDashboardMetaSerializer(read_only=True)
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
    data_inicio = serializers.DateField(read_only=True)
    data_fim = serializers.DateField(read_only=True)
