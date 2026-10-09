from django.db.models import Max
from rest_framework import serializers

from apps.sgd.models.arlo_field_mapping import ArloFieldMapping
from apps.sgd.services.arlo_mapping import CAMPOS, formatos_permitidos


class ArloFieldMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArloFieldMapping
        fields = ["id", "direcao", "campo_sgd", "coluna_arlo", "formato", "ordem", "ativo"]
        read_only_fields = ["id"]
        extra_kwargs = {"ordem": {"required": False}}

    def get_extra_kwargs(self):
        kwargs = super().get_extra_kwargs()
        if self.instance is not None:  # direção e campo identificam a linha; não mudam depois de criada
            for nome in ("direcao", "campo_sgd"):
                kwargs.setdefault(nome, {})["read_only"] = True
        return kwargs

    def validate_coluna_arlo(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("Informe o nome da coluna.")
        return valor

    def validate(self, attrs):
        atual = self.instance
        direcao = attrs.get("direcao") or atual.direcao
        campo = attrs.get("campo_sgd") or atual.campo_sgd
        formato = attrs.get("formato") or (atual.formato if atual else ArloFieldMapping.Formato.TEXTO)

        if campo not in CAMPOS[direcao]:
            raise serializers.ValidationError({"campo_sgd": f"Campo inválido para {direcao}: {sorted(CAMPOS[direcao])}."})
        if "formato" in attrs or atual is None:
            permitidos = formatos_permitidos(direcao, campo)
            if formato not in permitidos:
                raise serializers.ValidationError({"formato": f"Formato do campo '{campo}' deve ser um de {sorted(permitidos)}."})
        # O validador de unicidade do DRF é ignorado no PATCH (direção é read-only); checa à mão.
        coluna = attrs.get("coluna_arlo")
        if coluna and ArloFieldMapping.objects.filter(direcao=direcao, coluna_arlo=coluna).exclude(
            pk=getattr(atual, "pk", None),
        ).exists():
            raise serializers.ValidationError({"coluna_arlo": "Já existe um campo mapeado para esta coluna."})
        if atual is None and "ordem" not in attrs:
            ultimo = ArloFieldMapping.objects.filter(direcao=direcao).aggregate(m=Max("ordem"))["m"]
            attrs["ordem"] = (ultimo or 0) + 1
        return attrs
