"""Regras de unicidade de MembroFamilia/UPF, compartilhadas entre a API web e o sync SCA.

Espelha o padrão de `apps.sgp.services.activity_status`: exceções com
`field`/`sync_code`, funções puras que só validam e levantam erro — quem
chama decide como reportar (serializer web converte em ValidationError,
sync SCA converte em SyncEntityError).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError

from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.validators import validate_cpf as _validar_formato_cpf


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


REGRA_NEGOCIO_SYNC_CODES = {
    CPFInvalidoError.sync_code,
    CPFDuplicadoError.sync_code,
    TitularDuplicadoError.sync_code,
}


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
