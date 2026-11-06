from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from rest_framework import serializers

from apps.sgd.models.tipo_solicitacao import TipoSolicitacao
from apps.sgd.services import demand_request  # noqa: F401  registra os validadores
from apps.sgd.services.tipos_solicitacao import validadores_registrados


class SlugDeTipoField(serializers.CharField):
    """O slug de um tipo do catálogo, ativo ou não: quem exige tipo ativo é quem cria a solicitação."""

    default_error_messages = {"inexistente": '"{valor}" não é um tipo de solicitação válido.'}

    def to_internal_value(self, data):
        valor = super().to_internal_value(data)
        if not TipoSolicitacao.objects.filter(slug=valor).exists():
            self.fail("inexistente", valor=valor)
        return valor


def _exigir_rubrica_ativa(rubrica):
    if not rubrica.ativo:
        raise serializers.ValidationError("A rubrica informada está inativa.")
    return rubrica


class TipoSolicitacaoSerializer(serializers.ModelSerializer):
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = TipoSolicitacao
        fields = [
            "id", "slug", "nome", "rubrica", "rubrica_nome", "schema_campos", "validador", "ativo", "ordem",
            "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_slug(self, slug):
        if self.instance is not None and slug != self.instance.slug:
            raise serializers.ValidationError("O identificador não pode ser alterado: as solicitações o referenciam.")
        return slug

    def validate_rubrica(self, rubrica):
        return _exigir_rubrica_ativa(rubrica)

    def validate_schema_campos(self, schema):
        if not isinstance(schema, dict):
            raise serializers.ValidationError("Deve ser um objeto JSON Schema.")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise serializers.ValidationError(f"JSON Schema inválido: {exc.message}") from exc
        return schema

    def validate_validador(self, validador):
        if validador and validador not in validadores_registrados():
            raise serializers.ValidationError(f"Esperado um de: {validadores_registrados()}.")
        if self.instance is not None and validador != self.instance.validador:
            raise serializers.ValidationError(
                "A estratégia não pode ser alterada: ela decide onde o CPF é gravado e como é lido.",
            )
        return validador


class TipoRubricaSerializer(serializers.ModelSerializer):
    """Contrato de `/sgd/config/tipo-rubrica/`: uma linha por tipo do catálogo."""

    tipo = SlugDeTipoField(source="slug")
    rubrica_nome = serializers.CharField(source="rubrica.nome", read_only=True)

    class Meta:
        model = TipoSolicitacao
        fields = ["id", "tipo", "rubrica", "rubrica_nome", "ativo", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_rubrica(self, rubrica):
        return _exigir_rubrica_ativa(rubrica)

    def validate(self, attrs):
        if self.instance is None and TipoSolicitacao.objects.filter(slug=attrs["slug"], ativo=True).exists():
            raise serializers.ValidationError({"tipo": "Já existe um mapeamento ativo para este tipo de solicitação."})
        if self.instance is not None and attrs.get("slug", self.instance.slug) != self.instance.slug:
            raise serializers.ValidationError({"tipo": "O tipo de um mapeamento não pode ser alterado."})
        return attrs

    def create(self, validated_data):
        tipo = TipoSolicitacao.objects.get(slug=validated_data["slug"])
        return self.update(tipo, {"ativo": True, **validated_data})
