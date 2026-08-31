"""
Controle de leitura de campos sensíveis (LGPD, art. 5º II) por perfil de usuário.

Fonte única de verdade usada tanto pelos serializers da API quanto pela
exportação CSV (`apps.sgp.services.membro_export`), para que a mesma regra
de negócio não seja duplicada em dois lugares.

Referência: Issue #187 — Proteção de campos sensíveis (Saúde, Cor/Raça).
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.services.permissions import user_has_role

# Perfil -> conjunto de campos sensíveis que ele pode LER.
# Ajuste esta matriz conforme a política de acesso do PDHC evoluir; é o
# único lugar que precisa mudar.
SENSITIVE_FIELD_ROLES: dict[str, set[str]] = {
    "saude": {"super-admin", "ugp", "articulador-estadual", "adt-acr"},
    "cor_raca": {"super-admin", "ugp", "articulador-estadual", "adt-acr"},
}


def sensitive_fields_visible_to(user) -> set[str]:
    """Retorna os nomes dos campos sensíveis que `user` tem permissão de ler."""
    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    visible = set()
    for field, roles in SENSITIVE_FIELD_ROLES.items():
        if any(user_has_role(user, role) for role in roles):
            visible.add(field)
    return visible


class SensitiveFieldsSerializerMixin:
    """
    Remove do payload de saída os campos declarados em `sensitive_fields`
    (e seus companheiros `*_display`, se listados) quando o usuário da
    requisição não tem permissão de leitura sobre o campo sensível
    correspondente.

    Os campos são OMITIDOS da resposta — nunca retornados como `null` ou
    mascarados — para não sugerir a um perfil sem permissão que o dado existe.

    Uso:
        class MembroDetailSerializer(SensitiveFieldsSerializerMixin, serializers.ModelSerializer):
            sensitive_fields = {
                "saude": ("saude",),
                "cor_raca": ("cor_raca", "cor_raca_display"),
            }
    """

    sensitive_fields: dict[str, tuple[str, ...]] = {}

    def get_fields(self):
        fields = super().get_fields()
        for sensitive_field, output_field_names in self.sensitive_fields.items():
            if sensitive_field in self._sensitive_fields_visible():
                continue
            for name in output_field_names:
                fields.pop(name, None)

        return fields

    def to_internal_value(self, data):
        """
        Rejeita explicitamente (400) tentativa de escrita de campo sensível por
        quem não tem permissão de leitura sobre ele — nunca aceita e descarta
        o valor em silêncio, o que deixaria o autor da requisição sem saber
        que o campo não foi alterado.

        `get_fields()` já remove o campo de `self.fields` para esse usuário,
        então a checagem aqui olha o payload bruto (`data`), não `self.fields`.
        """
        if isinstance(data, dict):
            visible = self._sensitive_fields_visible()
            erros = {}
            for sensitive_field in self.sensitive_fields:
                if sensitive_field in visible:
                    continue
                if sensitive_field in data:
                    erros[sensitive_field] = (
                        "Você não tem permissão para alterar este campo."
                    )
            if erros:
                raise serializers.ValidationError(erros)
        return super().to_internal_value(data)

    def _sensitive_fields_visible(self):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        return sensitive_fields_visible_to(user)
