"""Regras de unicidade de MembroFamilia/UPF, compartilhadas entre a API web e o sync SCA.

Espelha o padrão de `apps.sgp.services.activity_status`: exceções com
`field`/`sync_code`, funções puras que só validam e levantam erro — quem
chama decide como reportar (serializer web converte em ValidationError,
sync SCA converte em SyncEntityError).
"""

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.sgp.models import MembroFamilia, UPF


class MembroRuleError(DjangoValidationError):
    """Base dos erros de unicidade de Membro/UPF. `field` indica onde o
    chamador deve reportar a mensagem. `sync_code` é o prefixo que o sync
    do SCA usa no `SyncEntityError` que devolve pro app."""

    field = "cpf"
    sync_code = "REGRA_MEMBRO_INVALIDA"

    def __init__(self, message):
        super().__init__(message, code="VALIDATION_ERROR")


class CPFDuplicadoError(MembroRuleError):
    sync_code = "CPF_DUPLICADO"

    def __init__(self, message, *, duplicado=None):
        super().__init__(message)
        self.duplicado = duplicado


class TitularDuplicadoError(MembroRuleError):
    field = "grau_parentesco"
    sync_code = "TITULAR_DUPLICADO"


REGRA_NEGOCIO_SYNC_CODES = {CPFDuplicadoError.sync_code, TitularDuplicadoError.sync_code}


def validar_cpf_unico(cpf, *, membro_atual=None):
    """Levanta CPFDuplicadoError se `cpf` já pertence a outro MembroFamilia.

    Unicidade GLOBAL — mesmo escopo da constraint `unique_cpf_global`.
    CPF vazio nunca é considerado duplicata.
    """
    if not cpf:
        return
    qs = MembroFamilia.objects.filter(cpf=cpf)
    if membro_atual is not None and membro_atual.pk:
        qs = qs.exclude(pk=membro_atual.pk)
    duplicado = qs.first()
    if duplicado:
        raise CPFDuplicadoError(
            f"Já existe um membro cadastrado com este CPF (UPF {duplicado.upf_id}).",
            duplicado=duplicado,
        )


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
