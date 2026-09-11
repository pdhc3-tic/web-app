from rest_framework import serializers

from apps.sgp.models import Cultura, EspecieAnimal, Production
from apps.sgp.serializers.catalogos import CatalogoProductionNestedSerializer


class ProductionSerializer(serializers.ModelSerializer):
    cultura = CatalogoProductionNestedSerializer(read_only=True)
    especie = CatalogoProductionNestedSerializer(read_only=True)
    cultura_id = serializers.PrimaryKeyRelatedField(
        queryset=Cultura.objects.filter(ativa=True),
        source="cultura",
        required=False,
        allow_null=True,
        write_only=True,
    )
    especie_id = serializers.PrimaryKeyRelatedField(
        queryset=EspecieAnimal.objects.filter(ativa=True),
        source="especie",
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Production
        fields = [
            "id",
            "upf",
            "tipo",
            "cultura",
            "cultura_id",
            "area_ha",
            "producao_estimada",
            "unidade_producao",
            "sementes_crioulas",
            "especie",
            "especie_id",
            "n_matrizes",
            "n_reprodutores",
            "n_jovens",
            "area_pastejo_ha",
            "sistema_criacao",
            "tipo_outra",
            "descricao_outra",
            "quantidade_produzida",
            "renda_estimada_mensal",
            "custo_anual",
            "observacoes",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "upf", "criado_em", "atualizado_em"]

    def validate(self, attrs):
        tipo = attrs.get("tipo", self.instance.tipo if self.instance else None)
        cultura = attrs.get("cultura", self.instance.cultura if self.instance else None)
        especie = attrs.get("especie", self.instance.especie if self.instance else None)
        tipo_outra = attrs.get(
            "tipo_outra",
            self.instance.tipo_outra if self.instance else None,
        )

        errors = {}
        if tipo == Production.TIPO_AGRICOLA:
            if not cultura:
                errors["cultura_id"] = "Cultura é obrigatória para produção agrícola."
            if especie:
                errors["especie_id"] = "Espécie deve ser nula para produção agrícola."
            if tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção agrícola."
        elif tipo == Production.TIPO_PECUARIA:
            if not especie:
                errors["especie_id"] = "Espécie é obrigatória para produção pecuária."
            if cultura:
                errors["cultura_id"] = "Cultura deve ser nula para produção pecuária."
            if tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade deve ser nulo para produção pecuária."
        elif tipo == Production.TIPO_OUTRA:
            if not tipo_outra:
                errors["tipo_outra"] = "Tipo de outra atividade é obrigatório."
            if cultura:
                errors["cultura_id"] = "Cultura deve ser nula para outra atividade."
            if especie:
                errors["especie_id"] = "Espécie deve ser nula para outra atividade."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
