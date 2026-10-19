from rest_framework import serializers

from apps.sgd.models.demand_type_rubrica_mapping import DemandTypeRubricaMapping


class DemandTypeRubricaMappingSerializer(serializers.ModelSerializer):
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = DemandTypeRubricaMapping
        fields = ["id", "tipo", "rubrica", "rubrica_nome", "ativo", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # O DRF converte a constraint parcial (condition=ativo) em UniqueValidator
        # incondicional em `tipo`, o que barraria também mapeamentos inativos.
        # A unicidade só entre ativos é checada em `validate`.
        extra_kwargs = {"tipo": {"validators": []}}

    def validate_rubrica(self, rubrica):
        if not rubrica.ativo:
            raise serializers.ValidationError("A rubrica informada está inativa.")
        return rubrica

    def validate(self, attrs):
        atual = self.instance
        tipo = attrs.get("tipo", getattr(atual, "tipo", None))
        ativo = attrs.get("ativo", getattr(atual, "ativo", True))
        # A constraint parcial não vira 400 sozinha no ModelSerializer; checa à mão
        # (a constraint no banco continua protegendo contra corrida).
        if ativo and DemandTypeRubricaMapping.objects.filter(tipo=tipo, ativo=True).exclude(
            pk=getattr(atual, "pk", None),
        ).exists():
            raise serializers.ValidationError(
                {"tipo": "Já existe um mapeamento ativo para este tipo de solicitação."}
            )
        return attrs
