"""Única fonte das regras de negócio de `Activity` (status, datas, participantes).

Consumido pela API web, pelo Django Admin e pelo sync do SCA, para que os
três apliquem exatamente a mesma regra. As regras em si
(`STATUS_TRANSITIONS`, `STATUS_TERMINAIS`, `has_evidencias()`) continuam em
`apps.sgp.models.activity` — este módulo só aplica.
"""

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.sgp.models import MembroFamilia
from apps.sgp.models.activity import STATUS_TRANSITIONS


class ActivityRuleError(DjangoValidationError):
    """Base de toda regra de negócio de Activity. `field` indica onde o
    chamador (serializer, admin form) deve reportar a mensagem. `sync_code`
    é o prefixo que o sync do SCA usa no `SyncEntityError` que devolve pro
    app, e o código que classifica a rejeição como conflito de regra de
    negócio em `conflict_log`."""

    field = "status"
    sync_code = "ATIVIDADE_REGRA_INVALIDA"

    def __init__(self, message):
        super().__init__(message, code="VALIDATION_ERROR")


class ActivityStatusError(ActivityRuleError):
    """Base dos erros de transição de status — "status", "justificativa" ou
    "data_inicio"."""

    sync_code = "TRANSICAO_INVALIDA"


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


class DataFimInvalidaError(ActivityRuleError):
    field = "data_fim"
    sync_code = "DATA_FIM_INVALIDA"


class MembroForaUPFError(ActivityRuleError):
    field = "membros_participantes"
    sync_code = "MEMBRO_FORA_UPF"


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


def _como_data(valor):
    """`datetime.datetime` tem `.date()`; `datetime.date` puro não. O payload
    de sync trafega `data_inicio`/`data_fim` como data (sem hora), enquanto o
    model/serializer web usa datetime — normaliza os dois para o mesmo tipo
    antes de comparar, senão `<` entre date e datetime levanta TypeError."""
    return valor.date() if hasattr(valor, "date") else valor


def validar_datas(data_inicio, data_fim):
    """Levanta DataFimInvalidaError se `data_fim` for anterior a `data_inicio`.

    Qualquer um dos dois ausente pula a checagem — quem chama decide os
    fallbacks (valor atual da atividade, se não vier no payload).
    """
    if not data_inicio or not data_fim:
        return
    if _como_data(data_fim) < _como_data(data_inicio):
        raise DataFimInvalidaError("data_fim não pode ser anterior a data_inicio.")


def validar_membros_participantes(upfs_ids, membros_ids):
    """Levanta MembroForaUPFError se algum de `membros_ids` não pertencer a
    nenhuma das UPFs em `upfs_ids`.

    Aceita ids (não instâncias) dos dois lados, para servir tanto o
    serializer web (que já tem os objetos, bastando `.pk`) quanto o sync do
    SCA (que só tem ids resolvidos do payload/uuid_map).
    """
    upfs_ids = set(upfs_ids or ())
    membros_ids = list(membros_ids or ())
    if not upfs_ids or not membros_ids:
        return
    invalidos = list(
        MembroFamilia.objects.filter(pk__in=membros_ids)
        .exclude(upf_id__in=upfs_ids)
        .values_list("pk", flat=True)
    )
    if invalidos:
        raise MembroForaUPFError(
            f"Membros {invalidos} não pertencem às UPFs participantes selecionadas."
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
