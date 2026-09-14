"""Única fonte da regra de transição de status de `Activity`.

Consumido pela API web, pelo Django Admin e pelo sync do SCA, para que os
três apliquem exatamente a mesma regra. As regras em si
(`STATUS_TRANSITIONS`, `STATUS_TERMINAIS`, `has_evidencias()`) continuam em
`apps.sgp.models.activity` — este módulo só aplica.
"""

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.sgp.models.activity import STATUS_TRANSITIONS


class ActivityStatusError(DjangoValidationError):
    """Base dos erros de transição. `field` indica onde o chamador (serializer,
    admin form) deve reportar a mensagem — "status", "justificativa" ou
    "data_inicio". `sync_code` é o prefixo que o sync do SCA usa no
    `SyncEntityError` que devolve pro app."""

    field = "status"
    sync_code = "TRANSICAO_INVALIDA"

    def __init__(self, message):
        super().__init__(message, code="VALIDATION_ERROR")


class TransicaoInvalidaError(ActivityStatusError):
    pass


class EvidenciaObrigatoriaError(ActivityStatusError):
    sync_code = "EVIDENCIA_OBRIGATORIA"


class JustificativaObrigatoriaError(ActivityStatusError):
    field = "justificativa"
    sync_code = "JUSTIFICATIVA_OBRIGATORIA"


class NovaDataObrigatoriaError(ActivityStatusError):
    field = "data_inicio"
    sync_code = "NOVA_DATA_OBRIGATORIA"


_STATUS_EXIGE_JUSTIFICATIVA = {"nao_realizada", "cancelada"}
_STATUS_INICIAIS_VALIDOS = {"planejado", "agendado"}


def validar_transicao(activity, novo_status, *, justificativa="", nova_data=None):
    """Levanta erro se a transição para `novo_status` não é permitida.

    `activity=None` (ou sem pk) representa criação. Não muta nem persiste
    nada — só valida. `justificativa`/`nova_data` já devem vir resolvidos
    pelo chamador (com os mesmos fallbacks que a API web sempre usou: se
    não vierem no payload, cai no valor atual da atividade).
    """
    is_new = activity is None or activity.pk is None
    status_atual = None if is_new else activity.status

    if is_new:
        if novo_status not in _STATUS_INICIAIS_VALIDOS:
            raise TransicaoInvalidaError(
                f"Ao criar uma atividade o status inicial deve ser "
                f"'planejado' ou 'agendado'. Recebido: '{novo_status}'."
            )
    elif novo_status != status_atual:
        permitidos = STATUS_TRANSITIONS.get(status_atual, set())
        if novo_status not in permitidos:
            raise TransicaoInvalidaError(
                f"Transição inválida: '{status_atual}' → '{novo_status}'. "
                f"Transições permitidas a partir de '{status_atual}': "
                f"{sorted(permitidos) if permitidos else ['nenhuma (estado terminal)']}"
            )

    if novo_status in _STATUS_EXIGE_JUSTIFICATIVA and not justificativa:
        raise JustificativaObrigatoriaError(
            f"Justificativa é obrigatória quando o status é '{novo_status}'."
        )

    if novo_status == "concluido":
        if is_new:
            raise EvidenciaObrigatoriaError(
                "Não é possível criar uma atividade já com status 'concluido'. "
                "Inicie como 'planejado' e avance o status progressivamente."
            )
        if not activity.has_evidencias():
            raise EvidenciaObrigatoriaError(
                "Não é possível concluir uma atividade sem ao menos "
                "uma foto ou documento vinculado. "
                "Adicione evidências antes de marcar como Concluído."
            )

    # Reagendar (sair de 'adiada' de volta pra 'agendado') exige uma nova
    # data — senão a atividade "reagendada" continua com a data antiga.
    if not is_new and status_atual == "adiada" and novo_status == "agendado":
        if not nova_data or nova_data == activity.data_inicio:
            raise NovaDataObrigatoriaError(
                "Reagendar uma atividade 'adiada' exige uma nova data de "
                "início, diferente da atual."
            )


def transition(activity, novo_status, *, usuario, justificativa="", nova_data=None):
    """Único ponto de mudança de status de uma Atividade.

    Valida (`validar_transicao`) e aplica os campos em memória — quem chama
    decide quando persistir (`activity.save(...)`). Usado pelo sync do SCA,
    que não tem a separação em duas fases (validar → salvar) que o
    serializer da API web e o `ModelForm` do Admin têm.

    `usuario` não é usado por esta função; reservado para uma trilha de
    auditoria futura.
    """
    validar_transicao(
        activity, novo_status, justificativa=justificativa, nova_data=nova_data
    )
    activity.status = novo_status
    if justificativa:
        activity.justificativa = justificativa
    if nova_data is not None:
        activity.data_inicio = nova_data
    return activity
