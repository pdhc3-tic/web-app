import re

from rest_framework import serializers
from validate_docbr import CPF as CPFValidator


def validate_cpf(value):
    digits = re.sub(r"\D", "", value)

    if len(digits) != 11:
        raise serializers.ValidationError(
            "CPF deve conter 11 dígitos numéricos"
        )

    if digits == digits[0] * 11:
        raise serializers.ValidationError(
            "CPF inválido: todos os dígitos são iguais"
        )

    cpf = CPFValidator()
    if not cpf.validate(digits):
        raise serializers.ValidationError(
            "CPF inválido: dígito verificador não confere"
        )

    return digits
