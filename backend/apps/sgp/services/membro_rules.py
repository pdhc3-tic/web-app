"""Regras de unicidade de MembroFamilia/UPF, compartilhadas entre a API web e o sync SCA.

Espelha o padrão de `apps.sgp.services.activity_status`: exceções com
`field`/`sync_code`, funções puras que só validam e levantam erro — quem
chama decide como reportar (serializer web converte em ValidationError,
sync SCA converte em SyncEntityError).
"""

import re
from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError

from apps.sgp.constants import SAUDE_CHOICES, SEGURIDADE_SOCIAL_CHOICES
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.validators import validate_cpf as _validar_formato_cpf

VALORES_SAUDE = [valor for valor, _ in SAUDE_CHOICES]
VALORES_SEGURIDADE_SOCIAL = [valor for valor, _ in SEGURIDADE_SOCIAL_CHOICES]


class MembroRuleError(DjangoValidationError):
    """Base dos erros de unicidade de Membro/UPF. `field` indica onde o
    chamador deve reportar a mensagem. `sync_code` é o prefixo que o sync
    do SCA usa no `SyncEntityError` que devolve pro app."""

    field = "cpf"
    sync_code = "REGRA_MEMBRO_INVALIDA"

    def __init__(self, message):
        super().__init__(message, code="VALIDATION_ERROR")


class CPFInvalidoError(MembroRuleError):
    """Formato incorreto ou dígito verificador inválido — mesma checagem que
    `apps.sgp.validators.validate_cpf`, agora também aplicada pelo sync."""

    sync_code = "CPF_INVALIDO"


class CPFDuplicadoError(MembroRuleError):
    sync_code = "CPF_DUPLICADO"

    def __init__(self, message, *, duplicado=None):
        super().__init__(message)
        self.duplicado = duplicado


class TitularDuplicadoError(MembroRuleError):
    field = "grau_parentesco"
    sync_code = "TITULAR_DUPLICADO"


class DataNascimentoFuturaError(MembroRuleError):
    field = "data_nascimento"
    sync_code = "DATA_NASCIMENTO_INVALIDA"


class SaudeInvalidaError(MembroRuleError):
    field = "saude"
    sync_code = "SAUDE_INVALIDA"


class SeguridadeSocialInvalidaError(MembroRuleError):
    field = "seguridade_social"
    sync_code = "SEGURIDADE_SOCIAL_INVALIDA"


REGRA_NEGOCIO_SYNC_CODES = {
    CPFInvalidoError.sync_code,
    CPFDuplicadoError.sync_code,
    TitularDuplicadoError.sync_code,
    DataNascimentoFuturaError.sync_code,
    SaudeInvalidaError.sync_code,
    SeguridadeSocialInvalidaError.sync_code,
}


def normalizar_cpf(cpf) -> str:
    """Só remove tudo que não é dígito — sem validar formato/dígito
    verificador. Usado na busca por identificador natural (`get_by_natural`),
    onde precisamos achar o registro mesmo que o CPF enviado esteja com
    máscara; a validação de formato em si acontece em `validar_cpf`, chamado
    antes de qualquer gravação."""
    return re.sub(r"\D", "", cpf or "")


def validar_cpf(cpf, *, membro_atual=None):
    """Normaliza, valida formato/dígito verificador e checa unicidade GLOBAL
    (mesmo escopo da constraint `unique_cpf_global`).

    CPF vazio retorna "" sem validar nada. Levanta `CPFInvalidoError` para
    formato/dígito inválido (mesma regra de `apps.sgp.validators.validate_cpf`,
    reaproveitada aqui) e `CPFDuplicadoError` para duplicata. Retorna o CPF
    normalizado (só dígitos) — é esse valor que o chamador deve persistir,
    nunca o texto bruto recebido.
    """
    if not cpf:
        return ""
    try:
        cpf_normalizado = _validar_formato_cpf(cpf)
    except DRFValidationError as exc:
        detail = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
        raise CPFInvalidoError(str(detail)) from exc

    qs = MembroFamilia.objects.filter(cpf=cpf_normalizado)
    if membro_atual is not None and membro_atual.pk:
        qs = qs.exclude(pk=membro_atual.pk)
    duplicado = qs.first()
    if duplicado:
        raise CPFDuplicadoError(
            f"Já existe um membro cadastrado com este CPF (UPF {duplicado.upf_id}).",
            duplicado=duplicado,
        )
    return cpf_normalizado


def validar_titular_unico(upf_id, *, membro_atual=None):
    """Levanta TitularDuplicadoError se a UPF `upf_id` já tem um titular
    diferente de `membro_atual`."""
    if not upf_id:
        return
    upf = UPF.objects.filter(pk=upf_id).only("id", "titular_id").first()
    if upf is None or not upf.titular_id:
        return
    if membro_atual is None or upf.titular_id != membro_atual.pk:
        raise TitularDuplicadoError("Já existe um titular cadastrado para esta UPF.")


def validar_data_nascimento(value):
    """Levanta DataNascimentoFuturaError se `value` for uma data futura.
    `value` ausente (None) não é validado."""
    if value and value > date.today():
        raise DataNascimentoFuturaError(
            "Data de nascimento não pode ser uma data futura"
        )
    return value


def validar_saude(value):
    """Levanta SaudeInvalidaError para valores fora do catálogo, duplicados,
    ou 'nenhuma' combinada com outras condições. `value` ausente (None) não
    é validado — quem chama decide se o campo é obrigatório."""
    if value is None:
        return value
    if not isinstance(value, list):
        raise SaudeInvalidaError("Saúde deve ser uma lista de strings")
    if len(value) != len(set(value)):
        raise SaudeInvalidaError("Condições de saúde não podem conter duplicidades.")
    for item in value:
        if item not in VALORES_SAUDE:
            raise SaudeInvalidaError(
                f"'{item}' não é um valor válido para saúde. "
                f"Valores permitidos: {', '.join(VALORES_SAUDE)}"
            )
    if "nenhuma" in value and len(value) > 1:
        raise SaudeInvalidaError(
            "A opção 'nenhuma' é mutuamente exclusiva com outras condições."
        )
    return value


def validar_seguridade_social(value):
    """Levanta SeguridadeSocialInvalidaError para valores fora do catálogo,
    duplicados, ou 'nenhum' combinado com outros benefícios. `value` ausente
    (None) não é validado."""
    if value is None:
        return value
    if not isinstance(value, list):
        raise SeguridadeSocialInvalidaError(
            "Seguridade social deve ser uma lista de strings."
        )
    if len(value) != len(set(value)):
        raise SeguridadeSocialInvalidaError(
            "Seguridade social não pode conter duplicidades."
        )
    for item in value:
        if item not in VALORES_SEGURIDADE_SOCIAL:
            raise SeguridadeSocialInvalidaError(
                f"'{item}' não é um valor válido para seguridade social. "
                f"Valores permitidos: {', '.join(VALORES_SEGURIDADE_SOCIAL)}"
            )
    if "nenhum" in value and len(value) > 1:
        raise SeguridadeSocialInvalidaError(
            "A opção 'nenhum' é mutuamente exclusiva com outros benefícios."
        )
    return value
